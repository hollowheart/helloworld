"""
Export all issues matching a JQL query from Jira Data Center to one JSON file.

Uses POST /rest/api/2/search with pagination.

After the main JQL export, direct child issues are included by default: issues whose
``parent`` is one of the matched keys (subtasks / hierarchy), and issues whose
``Epic Link`` points at one of those keys. Use ``--no-children`` to skip that step.

Environment variables (optional; CLI overrides):
  JIRA_BASE_URL   Base URL without trailing slash, e.g. https://jiradc.ext.net.nokia.com
  JIRA_TOKEN      Personal access token (PAT) or password
  JIRA_AUTH_MODE  "bearer" (default) or "basic" — use bearer when the server disables Basic auth
  JIRA_USER       Required only for basic: username for HTTP Basic auth

Examples (PowerShell):
  # PAT with Bearer (typical when Basic auth is disabled on the instance)
  $env:JIRA_BASE_URL="https://jiradc.ext.net.nokia.com"
  $env:JIRA_TOKEN="<your-pat>"
  python export_jira_search.py --output export.json

  # Legacy Basic (username + token/password)
  $env:JIRA_AUTH_MODE="basic"
  $env:JIRA_USER="kewang"
  $env:JIRA_TOKEN="<token-or-password>"
  python export_jira_search.py --output export.json
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any

import requests

DEFAULT_JQL = 'project = ffb and "Feature ID" ~ "CB015880-SR"'
SEARCH_PATH = "/rest/api/2/search"
# Jira JQL length limits vary; smaller chunks avoid HTTP 414 / parse errors.
_KEYS_PER_CHILD_JQL = 50


def _parse_jira_search_json(r: requests.Response, url: str) -> dict[str, Any]:
    """Parse Jira search JSON or raise SystemExit with a readable diagnostic."""
    ctype = (r.headers.get("Content-Type") or "").split(";")[0].strip().lower()
    raw = r.text or ""
    if not raw.strip():
        raise SystemExit(
            f"Jira returned an empty body (HTTP {r.status_code}, URL {url}). "
            "Check JIRA_BASE_URL (no trailing path), VPN, and that the host is Jira "
            "not a proxy or captive portal."
        )
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        snippet = raw[:800].replace("\n", " ")
        hint = ""
        if raw.lstrip().startswith("<"):
            hint = " Body looks like HTML (login page, proxy error, or WAF)."
        raise SystemExit(
            f"Jira response was not JSON (HTTP {r.status_code}, Content-Type: {ctype!r}, "
            f"URL {url}).{hint} First bytes: {snippet!r}. Underlying error: {e}"
        ) from e
    if not isinstance(data, dict):
        raise SystemExit(
            f"Jira search JSON was not an object (got {type(data).__name__}) at {url}"
        )
    return data


def _env(name: str, default: str | None = None) -> str | None:
    v = os.environ.get(name)
    return v if v else default


def fetch_all_issues(
    base_url: str,
    jql: str,
    max_results: int,
    session: requests.Session,
    *,
    on_jql_error: str = "exit",
) -> dict[str, Any]:
    """on_jql_error: 'exit' raises SystemExit; 'empty' returns issues=[] and optional warning."""
    base = base_url.rstrip("/")
    url = f"{base}{SEARCH_PATH}"
    all_issues: list[dict[str, Any]] = []
    start_at = 0
    total: int | None = None
    last_meta: dict[str, Any] = {}

    while True:
        body: dict[str, Any] = {
            "jql": jql,
            "startAt": start_at,
            "maxResults": max_results,
            "fields": ["*all"],
        }
        r = session.post(
            url,
            json=body,
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
        )
        if r.status_code != 200:
            hint = ""
            if r.status_code == 403 and "Basic Authentication has been disabled" in r.text:
                hint = (
                    "\n\nHint: this server expects a PAT with Bearer auth. "
                    "Use --auth-mode bearer (default) and only JIRA_BASE_URL + JIRA_TOKEN; "
                    "do not use HTTP Basic."
                )
            msg = f"Jira search failed HTTP {r.status_code}: {r.text[:2000]}{hint}"
            if on_jql_error == "empty":
                return {
                    "jql": jql,
                    "total": 0,
                    "issues": [],
                    "childFetchWarning": msg,
                }
            raise SystemExit(msg)
        try:
            data = _parse_jira_search_json(r, url)
        except SystemExit as err:
            if on_jql_error == "empty":
                return {
                    "jql": jql,
                    "total": 0,
                    "issues": [],
                    "childFetchWarning": str(err),
                }
            raise err
        last_meta = {
            k: data[k]
            for k in ("errorMessages", "warningMessages", "names", "schema")
            if k in data
        }
        if data.get("errorMessages"):
            err = "Jira returned errors: " + json.dumps(data["errorMessages"], indent=2)
            if on_jql_error == "empty":
                return {
                    "jql": jql,
                    "total": 0,
                    "issues": [],
                    "childFetchWarning": err,
                }
            raise SystemExit(err)

        issues = data.get("issues") or []
        if total is None:
            total = int(data.get("total", 0))
        all_issues.extend(issues)

        if not issues:
            break
        start_at += len(issues)
        if start_at >= total:
            break

    return {
        "jql": jql,
        "total": total if total is not None else len(all_issues),
        "issues": all_issues,
        **last_meta,
    }


def _chunks(keys: list[str], size: int) -> list[list[str]]:
    return [keys[i : i + size] for i in range(0, len(keys), size)]


def _jql_in_list(field_jql: str, keys: list[str]) -> str:
    inner = ", ".join(keys)
    return f"{field_jql} in ({inner})"


def fetch_direct_child_issues(
    base_url: str,
    parent_keys: list[str],
    max_results: int,
    session: requests.Session,
) -> tuple[list[dict[str, Any]], list[str]]:
    """
    Direct children: parent field (subtasks / hierarchy) and Epic Link (stories on epics).
    Returns (issues, warnings).
    """
    if not parent_keys:
        return [], []

    warnings: list[str] = []
    by_key: dict[str, dict[str, Any]] = {}

    for batch in _chunks(parent_keys, _KEYS_PER_CHILD_JQL):
        jql_p = _jql_in_list("parent", batch)
        res = fetch_all_issues(
            base_url, jql_p, max_results, session, on_jql_error="empty"
        )
        if res.get("childFetchWarning"):
            warnings.append(f"parent batch: {res['childFetchWarning'][:500]}")
        for issue in res["issues"]:
            by_key[issue["key"]] = issue

        jql_e = _jql_in_list('"Epic Link"', batch)
        res_e = fetch_all_issues(
            base_url, jql_e, max_results, session, on_jql_error="empty"
        )
        if res_e.get("childFetchWarning"):
            warnings.append(f"Epic Link batch: {res_e['childFetchWarning'][:500]}")
        for issue in res_e["issues"]:
            by_key[issue["key"]] = issue

    return list(by_key.values()), warnings


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--base-url",
        default=_env("JIRA_BASE_URL"),
        help="Jira base URL (default: JIRA_BASE_URL)",
    )
    p.add_argument(
        "--user",
        default=_env("JIRA_USER"),
        help="Username (default: JIRA_USER)",
    )
    p.add_argument(
        "--token",
        default=_env("JIRA_TOKEN"),
        help="PAT or password (default: JIRA_TOKEN)",
    )
    p.add_argument(
        "--auth-mode",
        choices=("bearer", "basic"),
        default=(_env("JIRA_AUTH_MODE") or "bearer").lower(),
        help="bearer = Authorization: Bearer <PAT> (default). basic = HTTP Basic user+token",
    )
    p.add_argument(
        "--jql",
        default=DEFAULT_JQL,
        help="JQL query",
    )
    p.add_argument(
        "--output",
        "-o",
        required=True,
        help="Output JSON file path",
    )
    p.add_argument(
        "--max-results",
        type=int,
        default=100,
        help="Page size per request (default: 100)",
    )
    p.add_argument(
        "--no-children",
        action="store_true",
        help="Do not add child issues (parent / Epic Link) to the export",
    )
    args = p.parse_args()

    if args.auth_mode == "basic":
        if not args.base_url or not args.user or not args.token:
            print(
                "Missing credentials for basic auth: JIRA_BASE_URL, JIRA_USER, JIRA_TOKEN "
                "(or --base-url, --user, --token)",
                file=sys.stderr,
            )
            sys.exit(1)
    else:
        if not args.base_url or not args.token:
            print(
                "Missing credentials for bearer auth: JIRA_BASE_URL, JIRA_TOKEN "
                "(or --base-url, --token)",
                file=sys.stderr,
            )
            sys.exit(1)

    session = requests.Session()
    if args.auth_mode == "basic":
        session.auth = (args.user, args.token)
    else:
        session.headers["Authorization"] = f"Bearer {args.token}"

    try:
        out = fetch_all_issues(
            args.base_url,
            args.jql,
            args.max_results,
            session,
        )
    except (requests.RequestException, ValueError) as e:
        print(f"Request failed: {e}", file=sys.stderr)
        sys.exit(1)

    primary_issues: list[dict[str, Any]] = out["issues"]
    primary_keys = {i["key"] for i in primary_issues}
    primary_total = out["total"]

    child_warnings: list[str] = []
    if not args.no_children and primary_keys:
        children, child_warnings = fetch_direct_child_issues(
            args.base_url,
            sorted(primary_keys),
            args.max_results,
            session,
        )
        extra = [c for c in children if c["key"] not in primary_keys]
        out["issuesMatchingJqlCount"] = len(primary_issues)
        out["childIssuesAddedCount"] = len(extra)
        out["issues"] = primary_issues + extra
        for w in child_warnings:
            print(w, file=sys.stderr)
    else:
        out["issuesMatchingJqlCount"] = len(primary_issues)
        out["childIssuesAddedCount"] = 0

    out["total"] = primary_total
    if child_warnings:
        out["childFetchWarnings"] = child_warnings

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2, ensure_ascii=False)

    n = len(out["issues"])
    msg = (
        f"Wrote {n} issue(s) to {args.output} "
        f"(JQL total: {primary_total}; +{out['childIssuesAddedCount']} child-only)"
    )
    print(msg)


if __name__ == "__main__":
    main()
