"""Create Teams chats and post HTML messages (optional @mention) via Microsoft Graph."""

from __future__ import annotations

import re
from typing import Any

import requests

from teams_graph.constants import GRAPH_BASE


class GraphTeamsClient:
    """
    Graph client using a caller-supplied access token (obtain via MSAL + refresh_token
    or any other delegated flow).
    """

    def __init__(self, access_token: str) -> None:
        self._access_token = access_token
        self._session = requests.Session()
        self._session.headers.update(
            {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json",
            }
        )

    def _post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        url = f"{GRAPH_BASE}{path}"
        r = self._session.post(url, json=payload, timeout=60)
        if not r.ok:
            raise RuntimeError(f"Graph {r.status_code}: {r.text}")
        return r.json() if r.text else {}

    def _get(self, path: str) -> dict[str, Any]:
        url = f"{GRAPH_BASE}{path}"
        r = self._session.get(url, timeout=60)
        if not r.ok:
            raise RuntimeError(f"Graph {r.status_code}: {r.text}")
        return r.json()

    def resolve_user_id(self, user_id_or_upn: str) -> str:
        """
        Return AAD object id. Accepts GUID or UPN/email.
        GET /users/{id | userPrincipalName}
        """
        if re.fullmatch(
            r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}",
            user_id_or_upn,
        ):
            return user_id_or_upn
        safe = requests.utils.quote(user_id_or_upn, safe="")
        data = self._get(f"/users/{safe}")
        return data["id"]

    def create_one_on_one_chat(self, other_user_id_or_upn: str) -> str:
        """
        Create a 1:1 chat with another user. Caller must be one of the two members.
        Returns chat id.
        """
        me = self._get("/me")
        my_id = me["id"]
        other_id = self.resolve_user_id(other_user_id_or_upn)
        payload = {
            "chatType": "oneOnOne",
            "members": [
                {
                    "@odata.type": "#microsoft.graph.aadUserConversationMember",
                    "roles": ["owner"],
                    "user@odata.bind": f"{GRAPH_BASE}/users('{my_id}')",
                },
                {
                    "@odata.type": "#microsoft.graph.aadUserConversationMember",
                    "roles": ["owner"],
                    "user@odata.bind": f"{GRAPH_BASE}/users('{other_id}')",
                },
            ],
        }
        data = self._post("/chats", payload)
        return data["id"]

    def create_group_chat(
        self,
        member_ids_or_upns: list[str],
        topic: str | None = None,
    ) -> str:
        """
        Create a group chat. All participants including the signed-in user must appear
        in `member_ids_or_upns` (use /me id for yourself if you prefer explicit list).
        Returns chat id.
        """
        if len(member_ids_or_upns) < 2:
            raise ValueError("group chat needs at least two members")
        members: list[dict[str, Any]] = []
        for i, u in enumerate(member_ids_or_upns):
            uid = self.resolve_user_id(u)
            members.append(
                {
                    "@odata.type": "#microsoft.graph.aadUserConversationMember",
                    "roles": ["owner"],
                    "user@odata.bind": f"{GRAPH_BASE}/users('{uid}')",
                }
            )
        payload: dict[str, Any] = {"chatType": "group", "members": members}
        if topic:
            payload["topic"] = topic
        data = self._post("/chats", payload)
        return data["id"]

    def send_html_message(self, chat_id: str, html: str) -> dict[str, Any]:
        """POST /chats/{id}/messages — body only, no mentions."""
        payload = {"body": {"contentType": "html", "content": html}}
        return self._post(f"/chats/{chat_id}/messages", payload)

    def send_html_message_with_mention(
        self,
        chat_id: str,
        html: str,
        *,
        mention_id: int,
        mention_text: str,
        mentioned_user_id: str,
        mentioned_display_name: str,
    ) -> dict[str, Any]:
        """
        HTML must contain a matching tag, e.g. <at id="0">Display Name</at>
        with mention_id=0, mention_text matching inner text (Graph requirement).
        """
        payload = {
            "body": {"contentType": "html", "content": html},
            "mentions": [
                {
                    "id": mention_id,
                    "mentionText": mention_text,
                    "mentioned": {
                        "user": {
                            "displayName": mentioned_display_name,
                            "id": mentioned_user_id,
                            "userIdentityType": "aadUser",
                        }
                    },
                }
            ],
        }
        return self._post(f"/chats/{chat_id}/messages", payload)
