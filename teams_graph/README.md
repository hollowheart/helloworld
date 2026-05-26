# Teams Graph — delegated OAuth + `refresh_token`

Create **1:1 or group** Teams chats and send **HTML** messages (optional **@mention**) using **Microsoft Graph** (`https://graph.microsoft.com/v1.0`), with **delegated** permissions. Intended flow:

1. User signs in with Microsoft (**OAuth 2.0 authorization code**).
2. Your **backend** exchanges the `code` for `access_token` + **`refresh_token`** (requires **`offline_access`** scope).
3. Backend stores **`refresh_token`** in a **database** (encrypted); use **`AZURE_CLIENT_SECRET`** + MSAL **`acquire_token_by_refresh_token`** to obtain fresh **`access_token`** before Graph calls.

## Azure AD app registration

1. **Azure Portal** → Microsoft Entra ID → **App registrations** → New registration.
2. **Supported account types**: per your org (often single tenant).
3. Add a **Web** redirect URI (e.g. `https://your-api.example.com/auth/microsoft/callback` or `https://localhost:8400/callback` for dev).
4. **Certificates & secrets** → New client secret → copy value once (**`AZURE_CLIENT_SECRET`**).
5. **API permissions** → **Delegated** → add Microsoft Graph:
   - `Chat.Create`
   - `Chat.ReadWrite` (covers posting messages in typical setups; align with least privilege if your tenant allows finer scopes)
   - `User.Read.All` (resolve UPN → object id; you may replace with `User.Read` + different UX if policy forbids `.All`)
   - `offline_access` (so the auth-code response includes **`refresh_token`**)
6. **Grant admin consent** if required by your tenant.

Record **Directory (tenant) ID** → `AZURE_TENANT_ID`, **Application (client) ID** → `AZURE_CLIENT_ID`.

## Environment variables

| Variable | Purpose |
|----------|---------|
| `AZURE_TENANT_ID` | Tenant UUID |
| `AZURE_CLIENT_ID` | App (client) id |
| `AZURE_CLIENT_SECRET` | Client secret (backend only) |
| `AZURE_REFRESH_TOKEN` | Stored delegated refresh token for the signed-in user (secret) |

Never commit secrets or tokens. Use Key Vault / DB encryption in production.

## Python API

```python
from teams_graph import (
    GraphTeamsClient,
    acquire_token_by_refresh_token,
    build_auth_code_url,
    exchange_auth_code_for_tokens,
)

# 1) First login: send user to browser
url = build_auth_code_url(
    tenant_id=os.environ["AZURE_TENANT_ID"],
    client_id=os.environ["AZURE_CLIENT_ID"],
    redirect_uri="https://localhost:8400/callback",
)

# 2) On redirect, exchange ?code=...
tokens = exchange_auth_code_for_tokens(
    tenant_id=os.environ["AZURE_TENANT_ID"],
    client_id=os.environ["AZURE_CLIENT_ID"],
    client_secret=os.environ["AZURE_CLIENT_SECRET"],
    auth_code=request.args["code"],
    redirect_uri="https://localhost:8400/callback",
)
# Persist tokens["refresh_token"] in DB (and rotate when MSAL returns a new one)

# 3) Later: refresh and call Graph
def access_token() -> str:
    t = acquire_token_by_refresh_token(
        tenant_id=os.environ["AZURE_TENANT_ID"],
        client_id=os.environ["AZURE_CLIENT_ID"],
        client_secret=os.environ["AZURE_CLIENT_SECRET"],
        refresh_token=row.refresh_token,
    )
    if "refresh_token" in t:
        row.refresh_token = t["refresh_token"]  # rotate if present
    return t["access_token"]

client = GraphTeamsClient(access_token())
chat_id = client.create_one_on_one_chat("colleague@company.com")
client.send_html_message(chat_id, "<p>Hello from <b>Graph</b></p>")

uid = client.resolve_user_id("colleague@company.com")
client.send_html_message_with_mention(
    chat_id,
    f'<div><at id="0">Colleague</at> please review.</div>',
    mention_id=0,
    mention_text="Colleague",
    mentioned_user_id=uid,
    mentioned_display_name="Colleague Name",
)
```

## CLI (local testing)

```powershell
$env:AZURE_TENANT_ID="..."
$env:AZURE_CLIENT_ID="..."
$env:AZURE_CLIENT_SECRET="..."
$env:AZURE_REFRESH_TOKEN="..."

python -m teams_graph.cli send-html --chat-id "19:xxx@thread.v2" --html "<p>Test</p>"
```

Other subcommands: `auth-url`, `exchange-code`, `refresh`, `create-1on1`, `mention`. See `teams_graph/cli.py`.

## References

- [Create chat](https://learn.microsoft.com/en-us/graph/api/chat-post)
- [Send chatMessage in a chat](https://learn.microsoft.com/en-us/graph/api/chatmessage-post)
- [Mentions](https://learn.microsoft.com/en-us/graph/teams-chat-mentions)

## Security notes

- Treat **`refresh_token`** like a password: **encrypt at rest**, rotate on use if returned anew, revoke on sign-out.
- Prefer **single-tenant** apps and **least-privilege** Graph scopes.
- This module is not a web framework: wire **`exchange_auth_code_for_tokens`** into your own OAuth callback route.
