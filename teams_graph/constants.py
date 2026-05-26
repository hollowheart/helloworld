GRAPH_BASE = "https://graph.microsoft.com/v1.0"

# Delegated v2 scopes (space-separated in URLs; here as list for MSAL)
DEFAULT_DELEGATED_SCOPES = [
    "https://graph.microsoft.com/Chat.Create",
    "https://graph.microsoft.com/Chat.ReadWrite",
    "https://graph.microsoft.com/User.Read.All",
    "offline_access",  # required for refresh_token in auth-code flow
]
