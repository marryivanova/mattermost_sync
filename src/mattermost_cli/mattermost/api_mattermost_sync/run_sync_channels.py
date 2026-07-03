from loguru import logger

from config.settings import settings
from src.mattermost_cli.helpers.models import Counters
from src.mattermost_cli.mattermost.active_directory.mattermost_sync_manager import (
    MattermostSyncManager,
)
from src.mattermost_cli.mattermost.api_mattermost_sync.mattermost_client import MattermostClient


def initialize_mattermost_client():
    return MattermostClient(
        token=settings.MATTERMOST_TOKEN,
        url=settings.MATTERMOST_API,
        timeout=settings.TIMEOUT,
        max_retries=settings.MAX_RETRIES,
        retry_delay=settings.RETRY_DELAY,
    )


def get_channels_data(client) -> dict:
    """Retrieve all channels and return as dictionary."""
    data = client.get_list_all_channels()
    return {
        channel["id"]: {
            "display_name": channel["display_name"],
            "team_id": channel["team_id"],
        }
        for channel in data
        if channel["display_name"]
        not in [
            settings.DEFAULT_TYPE_CHANNEL_OFF_TOPIC,
            settings.DEFAULT_TYPE_CHANNEL_TOWN_SQUARE,
        ]
    }


def _filter_name_default(client):
    data = client.get_list_all_channels()
    return {
        channel["id"]: {
            "display_name": channel["display_name"],
            "team_id": channel["team_id"],
        }
        for channel in data
        if channel["display_name"] not in ["Off-Topic", "Town Square"]
    }


def get_channel_groups(client, team_id) -> list:
    """Retrieve all groups associated with a channel"""
    try:
        return client.get_team_channels(team_id=team_id)
    except Exception as e:
        logger.error(f"Failed to get groups for channel {team_id}: {str(e)}")
        return []


def get_user_data(sync_manager, client) -> tuple[set, dict]:
    """Retrieve and return AD users and Mattermost users mapping."""
    ad_users = sync_manager.get_users_from_ad()
    ad_usernames = {user.username.lower() for user in ad_users}
    logger.info(f"Loaded {len(ad_usernames)} users from AD")

    all_mm_users = client.get_autocomplete().get("users", [])
    mm_user_map = {user["id"]: user["username"].lower() for user in all_mm_users}
    logger.info(f"Loaded {len(mm_user_map)} Mattermost users")

    return ad_usernames, mm_user_map


def process_channel(client, channel_id, channel_info, ad_usernames, mm_user_map) -> tuple[int, int]:
    """Process a single channel - sync members with AD. Returns (added_count, removed_count)."""
    counters = Counters()

    try:
        team_id = channel_info.get("team_id")
        if not team_id:
            logger.error(f"Channel {channel_id} has no team_id, skipping")
            return counters.added, counters.removed
        try:
            team_members = client.get_team_members(team_id)
            if not team_members:
                return counters.added, counters.removed
        except Exception as e:
            logger.error(f"Failed to get team members for team {team_id}: {str(e)}")
            return counters.added, counters.removed

        current_members = client.get_channel_members(channel_id)
        current_member_ids = {m["user_id"] for m in current_members}

        for user in team_members:
            user_id = user["user_id"]
            if user_id not in current_member_ids:
                add_response = client.add_user_to_channel(channel_id, user_id)
                if isinstance(add_response, dict) and "id" in add_response:
                    logger.info(f"Added user {user_id} to channel {channel_id}")
                    counters.added += 1

        valid_user_ids = [
            member["user_id"]
            for member in team_members
            if member.get("user_id")
            and mm_user_map.get(member["user_id"], "").lower() in ad_usernames
        ]

        logger.info(f"Team has {len(team_members)} members, {len(valid_user_ids)} valid in AD")

        current_members = client.get_channel_members(channel_id)
        current_member_ids = {m["user_id"] for m in current_members}

        users_to_add = [user_id for user_id in valid_user_ids if user_id not in current_member_ids]
        if users_to_add:
            try:
                client.add_members_channels(channel_id, users_to_add)
                counters.added += len(users_to_add)
                logger.info(f"Added {len(users_to_add)} users to channel.")
            except Exception as e:
                logger.error(f"Failed to add members to channel {channel_id}: {str(e)}")

        counters.removed = verify_channel_members(client, channel_id, ad_usernames, mm_user_map)

    except Exception as e:
        logger.error(f"Unexpected error processing channel {channel_id}: {str(e)}")

    return counters.added, counters.removed


def verify_channel_members(client, channel_id, ad_usernames, mm_user_map) -> int:
    """Check channel members and remove invalid users. Returns number of removed users."""
    removed = 0
    try:
        current_members = client.get_channel_members(channel_id)
        for member in current_members:
            user_id = member["user_id"]
            username = mm_user_map.get(user_id, "").lower()
            if username not in ad_usernames:
                try:
                    client.remove_user_from_channel(channel_id, user_id)
                    removed += 1
                except Exception as e:
                    logger.error(f"Failed to remove user {user_id}: {str(e)}")
    except Exception as e:
        logger.error(f"Failed to verify channel members: {str(e)}")
    return removed


def sync_channels():
    """Main function to sync channel members with team members and verify against AD."""
    try:
        client = initialize_mattermost_client()
        sync_manager = MattermostSyncManager(mattermost_client=client)

        channels_dict = get_channels_data(client)
        logger.info(f"Found {len(channels_dict)} channels to process")

        ad_usernames, mm_user_map = get_user_data(sync_manager, client)

        for channel_id, channel_info in channels_dict.items():
            process_channel(client, channel_id, channel_info, ad_usernames, mm_user_map)

        logger.info("\nCompleted channel synchronization")

    except Exception as e:
        logger.error(f"\nFailed to sync channels: {str(e)}")
        raise
