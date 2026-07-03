import typing as t

from loguru import logger

from config.settings import settings
from src.mattermost_cli.helpers.models import GroupInfo, UserInfo
from src.mattermost_cli.ldap.client import LDAPClient
from src.mattermost_cli.mattermost.api_mattermost_sync.mattermost_client import MattermostClient


class MattermostSyncManager:
    def __init__(self, mattermost_client: MattermostClient):
        self.client = mattermost_client

    @staticmethod
    def _create_ldap_client() -> LDAPClient:
        """Create and return LDAP client with settings."""
        return LDAPClient(
            server=settings.LDAP_SERVER,
            user=settings.LDAP_USER,
            password=settings.LDAP_PASSWORD,
            base_dn=settings.LDAP_SEARCH_BASE,
        )

    @staticmethod
    def _create_user_info(user_data: dict) -> UserInfo:
        """Create UserInfo from raw user data."""
        return UserInfo(
            username=user_data.get("SamAccountName", ""),
            name=user_data.get("Name", ""),
            enabled=bool(user_data.get("Enabled", False)),
            givenname=user_data.get("GivenName", ""),
            userprincipalname=user_data.get("UserPrincipalName", ""),
        )

    @staticmethod
    def get_all_users_from_ad(active_only: bool = True) -> t.List[UserInfo]:
        """Get users from AD with filter."""
        with LDAPClient(
            server=settings.LDAP_SERVER,
            user=settings.LDAP_USER,
            password=settings.LDAP_PASSWORD,
            base_dn=settings.LDAP_SEARCH_BASE,
        ) as ldap_client:
            raw_users = (
                ldap_client.get_enabled_users() if active_only else ldap_client.get_disabled_users()
            )

            return [
                UserInfo(
                    username=user.get("SamAccountName", ""),
                    name=user.get("Name", ""),
                    enabled=bool(user.get("Enabled", False)),
                    givenname=user.get("GivenName", ""),
                    userprincipalname=user.get("UserPrincipalName", ""),
                )
                for user in raw_users
            ]

    @staticmethod
    def get_users_from_ad(active_only: bool = True) -> t.List[UserInfo]:
        """Get users from AD with active/inactive filter."""
        with MattermostSyncManager._create_ldap_client() as ldap_client:
            raw_users = (
                ldap_client.get_enabled_users() if active_only else ldap_client.get_disabled_users()
            )
            return [MattermostSyncManager._create_user_info(user) for user in raw_users]

    @staticmethod
    def get_user_only_group() -> t.List[GroupInfo]:
        """Get groups with their members from AD."""
        with MattermostSyncManager._create_ldap_client() as ldap_client:
            raw_groups = ldap_client.get_mattermost_groups_with_users()

            groups: list[GroupInfo] = []
            for group in raw_groups:
                members = [
                    MattermostSyncManager._create_user_info(user)
                    for user in group.get("members", [])
                ]

                groups.append(
                    GroupInfo(
                        name=group.get("name", ""),
                        dn=group.get("dn", ""),
                        member_count=len(members),
                        members=members,
                    )
                )

            return groups

    def _get_ad_usernames(self) -> set[str]:
        """Get set of all usernames from AD groups."""
        ad_groups = self.get_user_only_group()
        return {
            user.username.lower() for group in ad_groups for user in group.members if user.username
        }

    def _get_mm_user_map(self) -> dict[str, str]:
        """Get mapping of Mattermost user IDs to usernames."""
        all_mm_users = self._get_all_mattermost_users()
        return {user["id"]: user["username"].lower() for user in all_mm_users}

    @staticmethod
    def _verify_members_against_ad(
        members: list[dict],
        mm_user_map: dict[str, str],
        ad_usernames: set[str],
        entity_type: str,
        entity_id: str,
        remove_callback: t.Callable[[str, str], None],
    ) -> None:
        """Common verification logic for teams/channels."""
        logger.info(f"\nStarting AD verification for {entity_type} {entity_id}")

        for member in members:
            user_id = member["user_id"]
            username = mm_user_map.get(user_id)

            if not username:
                logger.warning(f"Could not find username for user ID {user_id}")
                remove_callback(entity_id, user_id)
                continue

            if username not in ad_usernames:
                logger.info(f"User {username} not found in AD, removing from {entity_type}")
                remove_callback(entity_id, user_id)
            else:
                logger.debug(f"User {username} verified in AD")

        logger.info(f"\nCompleted {entity_type} member verification")

    def verify_team_members_against_ad(self, team_id: str) -> None:
        """Verifies all team members exist in AD and removes those who don't."""
        try:
            team_members = self.client.get_team_members(team_id)
            mm_user_map = self._get_mm_user_map()
            ad_usernames = self._get_ad_usernames()

            self._verify_members_against_ad(
                members=team_members,
                mm_user_map=mm_user_map,
                ad_usernames=ad_usernames,
                entity_type="team",
                entity_id=team_id,
                remove_callback=self.client.delete_users_for_team,
            )
        except Exception as e:
            logger.error(f"\nFailed to verify team members against AD: {str(e)}")
            raise

    def channels_verify_team_members_against_ad(self, channel_id: str) -> None:
        """Verifies all channel members exist in AD and removes those who don't."""
        try:
            channel_members = self.client.get_channel_members(channel_id)
            mm_user_map = self._get_mm_user_map()
            ad_usernames = self._get_ad_groups()

            self._verify_members_against_ad(
                members=channel_members,
                mm_user_map=mm_user_map,
                ad_usernames=ad_usernames,
                entity_type="channel",
                entity_id=channel_id,
                remove_callback=self.client.delete_user_from_channel,
            )
        except Exception as e:
            logger.error(f"\nFailed to verify channel members against AD: {str(e)}")
            raise

    def _get_all_mattermost_users(self) -> list:
        """Retrieves all Mattermost users."""
        data = self.client.get_autocomplete()
        return data.get("users", []) if data else []
