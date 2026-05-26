"""
CLI examples for Teams Graph (delegated + refresh_token).

Set environment variables (see teams_graph/README.md), then e.g.:

  python -m teams_graph.cli auth-url --redirect-uri https://localhost:8400/callback
  python -m teams_graph.cli exchange-code --code "<paste>" --redirect-uri https://localhost:8400/callback
  python -m teams_graph.cli create-1on1 --other user@company.com
  python -m teams_graph.cli send-html --chat-id "<id>" --html "<p>Hello</p>"
"""

from __future__ import annotations

import argparse
import json
import os
import sys

from teams_graph.client import GraphTeamsClient
from teams_graph.msal_backend import (
    acquire_token_by_refresh_token,
    build_auth_code_url,
    exchange_auth_code_for_tokens,
)


def _env(name: str) -> str:
    v = os.environ.get(name, "").strip()
    if not v:
        raise SystemExit(f"Missing environment variable: {name}")
    return v


def cmd_auth_url(args: argparse.Namespace) -> None:
    url = build_auth_code_url(
        tenant_id=_env("AZURE_TENANT_ID"),
        client_id=_env("AZURE_CLIENT_ID"),
        redirect_uri=args.redirect_uri,
    )
    print(url)


def cmd_exchange_code(args: argparse.Namespace) -> None:
    result = exchange_auth_code_for_tokens(
        tenant_id=_env("AZURE_TENANT_ID"),
        client_id=_env("AZURE_CLIENT_ID"),
        client_secret=_env("AZURE_CLIENT_SECRET"),
        auth_code=args.code,
        redirect_uri=args.redirect_uri,
    )
    print(json.dumps(result, indent=2))
    if "refresh_token" in result:
        print("\n# Store refresh_token in your DB; treat as a secret.", file=sys.stderr)


def cmd_refresh(args: argparse.Namespace) -> None:
    result = acquire_token_by_refresh_token(
        tenant_id=_env("AZURE_TENANT_ID"),
        client_id=_env("AZURE_CLIENT_ID"),
        client_secret=_env("AZURE_CLIENT_SECRET"),
        refresh_token=_env("AZURE_REFRESH_TOKEN"),
    )
    if args.print_access_token:
        print(result["access_token"])
    else:
        redacted = {k: v for k, v in result.items() if k != "access_token"}
        redacted["access_token"] = "(redacted)"
        print(json.dumps(redacted, indent=2))


def _client_from_refresh() -> GraphTeamsClient:
    result = acquire_token_by_refresh_token(
        tenant_id=_env("AZURE_TENANT_ID"),
        client_id=_env("AZURE_CLIENT_ID"),
        client_secret=_env("AZURE_CLIENT_SECRET"),
        refresh_token=_env("AZURE_REFRESH_TOKEN"),
    )
    return GraphTeamsClient(result["access_token"])


def cmd_create_1on1(args: argparse.Namespace) -> None:
    client = _client_from_refresh()
    chat_id = client.create_one_on_one_chat(args.other)
    print(chat_id)


def cmd_send_html(args: argparse.Namespace) -> None:
    client = _client_from_refresh()
    out = client.send_html_message(args.chat_id, args.html)
    print(json.dumps(out, indent=2))


def cmd_mention(args: argparse.Namespace) -> None:
    client = _client_from_refresh()
    uid = client.resolve_user_id(args.mentioned_user)
    html = (
        f'<div><at id="0">{args.mention_text}</at> {args.tail_html}</div>'
    )
    out = client.send_html_message_with_mention(
        args.chat_id,
        html,
        mention_id=0,
        mention_text=args.mention_text,
        mentioned_user_id=uid,
        mentioned_display_name=args.display_name,
    )
    print(json.dumps(out, indent=2))


def cmd_create_group(args: argparse.Namespace) -> None:
    client = _client_from_refresh()
    members = [m.strip() for m in args.members.split(",") if m.strip()]
    chat_id = client.create_group_chat(members, topic=args.topic or None)
    print(chat_id)


def main() -> None:
    p = argparse.ArgumentParser(description="Teams Graph delegated helpers")
    sub = p.add_subparsers(dest="cmd", required=True)

    s1 = sub.add_parser("auth-url", help="Print browser OAuth URL (auth code flow)")
    s1.add_argument("--redirect-uri", required=True)
    s1.set_defaults(func=cmd_auth_url)

    s2 = sub.add_parser("exchange-code", help="Exchange auth code for tokens (print JSON)")
    s2.add_argument("--code", required=True)
    s2.add_argument("--redirect-uri", required=True)
    s2.set_defaults(func=cmd_exchange_code)

    s3 = sub.add_parser("refresh", help="Use refresh_token to get a new access token")
    s3.add_argument(
        "--print-access-token",
        action="store_true",
        help="Print raw access token to stdout (avoid in shared logs)",
    )
    s3.set_defaults(func=cmd_refresh)

    s4 = sub.add_parser("create-1on1", help="Create 1:1 chat with other user (UPN or id)")
    s4.add_argument("--other", required=True)
    s4.set_defaults(func=cmd_create_1on1)

    sg = sub.add_parser(
        "create-group",
        help="Create group chat; members is comma-separated UPNs/ids (must include you)",
    )
    sg.add_argument("--members", required=True, help="e.g. me@x.com,you@x.com")
    sg.add_argument("--topic", default="")
    sg.set_defaults(func=cmd_create_group)

    s5 = sub.add_parser("send-html", help="Post HTML message to existing chat id")
    s5.add_argument("--chat-id", required=True)
    s5.add_argument("--html", required=True)
    s5.set_defaults(func=cmd_send_html)

    s6 = sub.add_parser("mention", help="Post HTML with @mention (mention id 0)")
    s6.add_argument("--chat-id", required=True)
    s6.add_argument("--mentioned-user", required=True, help="UPN or object id of mentioned user")
    s6.add_argument("--mention-text", required=True, help="Must match text inside <at>…</at>")
    s6.add_argument("--display-name", required=True)
    s6.add_argument("--tail-html", default="", help="HTML after the mention tag")
    s6.set_defaults(func=cmd_mention)

    args = p.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
