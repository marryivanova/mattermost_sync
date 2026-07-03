from loguru import logger

from config.settings import settings
from src.mattermost_backend.mattermost.active_directory.mattermost_sync_manager import (
    MattermostSyncManager,
)
from src.mattermost_backend.mattermost.api_mattermost_sync.mattermost_client import MattermostClient

client = MattermostClient(
    token=settings.MATTERMOST_TOKEN,
    url=settings.MATTERMOST_API,
    timeout=settings.TIMEOUT,
    max_retries=settings.MAX_RETRIES,
    retry_delay=settings.RETRY_DELAY,
)


def sync_group_users_to_team(team_id: str) -> dict[str, list[str]]:
    """
    Synchronizes users between groups and a team.
    For each group in the team, checks if there are users in the group but not in the team,
    and adds those missing users to the team.
    """
    added_users_by_group: dict[str, list[str]] = {}

    # Get current team members
    team_member_ids = _get_team_member_ids(team_id)
    if team_member_ids is None:
        return added_users_by_group

    # Get groups associated with the team
    team_groups = _get_team_groups(team_id)
    if not team_groups:
        return added_users_by_group

    logger.info(f"Found {len(team_groups)} groups in team {team_id}")

    for group in team_groups:
        group_id = group.get("id")
        if not group_id:
            continue

        added_users = _process_group_users(group_id, team_member_ids, team_id)
        if added_users:
            added_users_by_group[group_id] = added_users

    # Verify team members -> Active Directory
    _verify_team_members_against_ad(team_id)

    return added_users_by_group


def _get_team_member_ids(team_id: str) -> set[str] | None:
    """Retrieve team member IDs from Mattermost API."""
    try:
        team_members = client.get_team_members(team_id)
        return {member["user_id"] for member in team_members}
    except Exception as e:
        logger.error(f"Failed to fetch team members: {e}")
        return None


def _get_team_groups(team_id: str) -> list[dict]:
    """Retrieve groups associated with a team from Mattermost API."""
    try:
        team_groups_response = client.get_team_id_by_groups(team_id)
        if isinstance(team_groups_response, dict):
            return team_groups_response.get("groups", [])
        return []
    except Exception as e:
        logger.error(f"Failed to fetch team groups: {e}")
        return []


def _process_group_users(group_id: str, team_member_ids: set[str], team_id: str) -> list[str]:
    """Process a single group to find and add missing users to the team."""
    try:
        group_members_data = client.get_group_members(group_id)
        if not isinstance(group_members_data, dict) or "members" not in group_members_data:
            return []

        group_members = group_members_data["members"]
        logger.info(f"Processing {len(group_members)} users in group {group_id}")

        group_member_ids = _extract_user_ids_from_members(group_members)
        missing_user_ids = group_member_ids - team_member_ids

        if not missing_user_ids:
            logger.info(f"All users from group {group_id} are already in the team")
            return []

        return _add_users_to_team(team_id, group_id, missing_user_ids)
    except Exception as e:
        logger.error(f"Unexpected error processing group {group_id}: {e}")
        return []


def _extract_user_ids_from_members(members: list[dict]) -> set[str]:
    """Extracts user IDs from member data."""
    return {member["id"] for member in members if member.get("id")}


def _add_users_to_team(team_id: str, group_id: str, user_ids: set[str]) -> list[str]:
    """Adds multiple users to a team."""
    added_users: list[str] = []

    for user_id in user_ids:
        try:
            client.add_user_to_team(team_id, user_id)
            added_users.append(user_id)
            logger.info(f"Added user {user_id} to team {team_id} from group {group_id}")
        except Exception as e:
            logger.error(f"Failed to add user {user_id} to team: {e}")

    if added_users:
        logger.info(f"Added {len(added_users)} users from group {group_id} to team")

    return added_users


def _verify_team_members_against_ad(team_id: str) -> None:
    """Verify team members against Active Directory."""
    sync_manager = MattermostSyncManager(mattermost_client=client)
    sync_manager.verify_team_members_against_ad(team_id)
