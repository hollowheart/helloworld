"""Delegated token acquisition: auth code (first login) and refresh_token (backend)."""

from __future__ import annotations

import urllib.parse
from typing import Any

import msal

from teams_graph.constants import DEFAULT_DELEGATED_SCOPES


def _authority(tenant_id: str) -> str:
    return f"https://login.microsoftonline.com/{tenant_id}"


def build_auth_code_url(
    tenant_id: str,
    client_id: str,
    redirect_uri: str,
    scopes: list[str] | None = None,
    state: str | None = None,
    prompt: str | None = None,
) -> str:
    """
    Build the Microsoft identity platform authorize URL for the auth-code flow.
    User opens this URL in a browser, signs in, and is redirected to redirect_uri with ?code=...
    """
    scopes = scopes or DEFAULT_DELEGATED_SCOPES
    app = msal.PublicClientApplication(client_id, authority=_authority(tenant_id))
    return app.get_authorization_request_url(
        scopes,
        redirect_uri=redirect_uri,
        state=state,
        prompt=prompt,
    )


def exchange_auth_code_for_tokens(
    tenant_id: str,
    client_id: str,
    client_secret: str,
    auth_code: str,
    redirect_uri: str,
    scopes: list[str] | None = None,
) -> dict[str, Any]:
    """
    Exchange authorization code for tokens (web backend callback).
    Persist result['refresh_token'] (and optionally cache the full result) in your DB.
    """
    scopes = scopes or DEFAULT_DELEGATED_SCOPES
    app = msal.ConfidentialClientApplication(
        client_id,
        client_credential=client_secret,
        authority=_authority(tenant_id),
    )
    result = app.acquire_token_by_authorization_code(
        auth_code,
        scopes=scopes,
        redirect_uri=redirect_uri,
    )
    if "access_token" not in result:
        raise RuntimeError(result.get("error_description") or result.get("error") or str(result))
    return result


def acquire_token_by_refresh_token(
    tenant_id: str,
    client_id: str,
    client_secret: str,
    refresh_token: str,
    scopes: list[str] | None = None,
) -> dict[str, Any]:
    """
    Refresh delegated access (backend job): store refresh_token from initial
    auth-code exchange, then call this to obtain a new access_token (and usually
    a rotated refresh_token — persist the new refresh_token if returned).
    """
    scopes = scopes or DEFAULT_DELEGATED_SCOPES
    app = msal.ConfidentialClientApplication(
        client_id,
        client_credential=client_secret,
        authority=_authority(tenant_id),
    )
    result = app.acquire_token_by_refresh_token(refresh_token, scopes=scopes)
    if "access_token" not in result:
        raise RuntimeError(result.get("error_description") or result.get("error") or str(result))
    return result


def parse_auth_redirect(query_string: str) -> dict[str, str]:
    """Parse ?code=...&state=... from redirect URL query string."""
    qs = query_string.lstrip("?")
    return dict(urllib.parse.parse_qsl(qs, keep_blank_values=True))
