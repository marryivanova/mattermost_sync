import typing as t
from time import sleep
from urllib.parse import urljoin

import requests


class MattermostClient:
    """Client for interacting with Mattermost API."""

    def __init__(
        self,
        token: str,
        url: str,
        timeout: int = 30,
        max_retries: int = 3,
        retry_delay: float = 1.0,
    ):
        self.token = token
        self.url = url.rstrip("/")
        self.timeout = timeout
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
        }

    def _make_request(self, method: str, endpoint: str, **kwargs) -> t.Optional[t.Dict[str, t.Any]]:
        """Internal method to make HTTP requests with retry logic."""
        url = urljoin(f"{self.url}/", endpoint)
        kwargs.setdefault("headers", self.headers)
        kwargs.setdefault("timeout", self.timeout)

        last_exception = None
        for attempt in range(1, self.max_retries + 1):
            try:
                response = requests.request(method, url, **kwargs)
                response.raise_for_status()
                return response.json() if response.content else None
            except requests.exceptions.RequestException as e:
                last_exception = e
                if attempt < self.max_retries:
                    sleep(self.retry_delay * attempt)

        raise last_exception or Exception("Request failed")

    def get_groups(self) -> t.Dict[str, t.Any]:
        """Get all groups from Mattermost."""
        return self._make_request("get", "api/v4/groups") or {}

    def create_group(self, group_data: t.Dict[str, t.Any]) -> t.Dict[str, t.Any]:
        """Create a new group in Mattermost."""
        return self._make_request("post", "api/v4/groups", json=group_data)

    def get_group_members(self, group_id: str) -> t.List[t.Dict[str, t.Any]]:
        """Get members of a specific group."""
        return self._make_request("get", f"api/v4/groups/{group_id}/members") or []

    def add_user_to_group(self, group_id: str, user_id: str) -> t.Dict[str, t.Any]:
        """Add user to group."""
        return self._make_request(
            "post", f"api/v4/groups/{group_id}/members", json={"user_id": user_id}
        )

    def remove_user_from_group(self, group_id: str, user_id: str) -> t.Dict[str, t.Any]:
        """Remove user from group."""
        return self._make_request("delete", f"api/v4/groups/{group_id}/members/{user_id}")

    def get_autocomplete(self):
        """Get user only autocomplete"""
        return self._make_request("get", f"api/v4/users/autocomplete")

    def get_a_team_member(self, team_id, user_id):
        """Get user by team"""
        return self._make_request("get", f"api/v4/teams/{team_id}/members/{user_id}")

    def get_user_groups(self, user_id: str) -> t.List[t.Dict[str, t.Any]]:
        """Get groups for a specific user."""
        return self._make_request("get", f"api/v4/users/{user_id}/groups") or []

    def get_group_channels(self, group_id: str) -> t.List[t.Dict[str, t.Any]]:
        """Get channels associated with a group."""
        return self._make_request("get", f"api/v4/groups/{group_id}/channels") or []

    def get_list_all_channels(self):
        """Get a list of all channels"""
        return self._make_request("get", f"api/v4/channels") or []

    def add_members_channels(self, channel_id: str, user_id: str):
        """Get a list of all channels"""
        data = {"user_id": user_id, "channel_id": channel_id}
        return self._make_request("get", f"api/v4/channels/{channel_id}/members", json=data) or []

    def get_channel_members(self, channel_id: str):
        """Get channel members"""
        return self._make_request("get", f"api/v4/channels/{channel_id}/members") or []

    def delete_user_from_channel(self, channel_id: str, user_id: str):
        """Remove user from channel"""
        return self._make_request("get", f"api/v4/channels/{channel_id}/members/{user_id}") or []

    def get_channel_groups(self, channel_id: str):
        """Get channel groups"""
        return self._make_request("get", f"api/v4/channels/{channel_id}/groups") or []

    def get_team_channels(self, team_id: str) -> t.List[t.Dict[str, t.Any]]:
        """Get channels for a team."""
        return self._make_request("get", f"api/v4/teams/{team_id}/channels") or []

    def get_invite_only_teams(self):
        """Get full list Team only open_invite type"""
        teams = self._make_request("get", "api/v4/teams")
        invite_only_teams = [team for team in teams if not team.get("allow_open_invite", True)]
        return invite_only_teams

    def get_list_team(self):
        """Get full list Team"""
        return self._make_request("post", f"api/v4/teams")

    def add_user_to_channel(self, channel_id: str, user_id: str) -> t.Dict[str, t.Any]:
        """Add user to channel."""
        return self._make_request(
            "post", f"api/v4/channels/{channel_id}/members", json={"user_id": user_id}
        )

    def update_channel_member_scheme_roles(
        self, channel_id: str, user_id: str, scheme_roles: t.Dict[str, bool]
    ) -> t.Dict[str, t.Any]:
        """Update channel member scheme roles."""
        return self._make_request(
            "put",
            f"api/v4/channels/{channel_id}/members/{user_id}/schemeRoles",
            json=scheme_roles,
        )

    def get_team_members(self, team_id) -> t.List[t.Dict[str, t.Any]]:
        """Get members of a specific team."""
        return self._make_request("get", f"api/v4/teams/{team_id}/members") or []

    def get_team_groups(self, team_id):
        """Get groups linked to a specific team."""
        return self._make_request("get", f"api/v4/teams/{team_id}/groups") or []

    def add_user_to_team(self, team_id: str, user_id: str) -> t.Dict[str, t.Any]:
        """Add user teams (member)"""
        data = {"team_id": team_id, "user_id": user_id}
        return self._make_request(
            "post",
            f"api/v4/teams/{team_id}/members",
            json=data,
        )

    def get_team_id_by_groups(self, team_id):
        """Get group by team_id"""
        return self._make_request("get", f"api/v4/teams/{team_id}/groups")

    def delete_users_for_team(self, team_id, user_id):
        """Remove user from team"""
        return self._make_request("delete", f"api/v4/teams/{team_id}/members/{user_id}")
