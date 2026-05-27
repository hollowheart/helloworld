GRAPH_BASE = "https://graph.microsoft.com/v1.0"

# Delegated v2 scopes (space-separated in URLs; here as list for MSAL)
# Do NOT add "offline_access", "openid", or "profile" here — MSAL adds them
# internally; passing them raises: ValueError reserved scope.
DEFAULT_DELEGATED_SCOPES = [
    "https://graph.microsoft.com/Chat.Create",
    "https://graph.microsoft.com/Chat.ReadWrite",
    "https://graph.microsoft.com/User.Read.All",
]
