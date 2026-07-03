from contextlib import contextmanager
from datetime import datetime
from typing import Optional

import typer
from loguru import logger

from config.database import get_db
from config.settings import settings
from db.repositories.command_logs_repository import CommandLogsRepository
from src.mattermost_backend.helpers.models import (
    CommandLog,
    ResultChannel,
    ResultTeams,
    Status,
    SyncChannelsParams,
    SyncResult,
)
from src.mattermost_backend.mattermost.active_directory.mattermost_sync_manager import (
    MattermostSyncManager,
)
from src.mattermost_backend.mattermost.api_mattermost_sync.mattermost_client import MattermostClient
from src.mattermost_backend.mattermost.api_mattermost_sync.run_script_teams import (
    client,
    sync_group_users_to_team,
)
from src.mattermost_backend.mattermost.api_mattermost_sync.run_sync_channels import (
    get_channels_data,
    get_user_data,
    process_channel,
)


class BaseSynchronizer:
    def __init__(self, entity_name: Optional[str], dry_run: bool, command_name: str):
        self.entity_name = entity_name
        self.dry_run = dry_run
        self.command_name = command_name
        self.mm_client = MattermostClient(
            token=settings.MATTERMOST_TOKEN,
            url=settings.MATTERMOST_API,
            timeout=settings.TIMEOUT,
            max_retries=settings.MAX_RETRIES,
            retry_delay=settings.RETRY_DELAY,
        )
        self.start_time = datetime.now()
        self.log_data = self._initialize_log_data()

    def _initialize_log_data(self) -> CommandLog:
        """Initialize command log data structure"""
        return CommandLog(
            command_name=self.command_name,
            team_name=(
                self.entity_name if self.entity_name else f"all_{self.command_name.split('_')[-1]}s"
            ),
            execution_start=self.start_time,
            dry_run=self.dry_run,
        )

    def _log_start(self, entity_type: str = "entities"):
        """Log command start with parameters"""
        logger.info(f"=== Starting {self.command_name} command ===")
        logger.info("Command parameters:")
        logger.info(f"  • dry_run: {'Yes (test mode)' if self.dry_run else 'No (real changes)'}")
        logger.info(
            f"  • {entity_type}: {self.entity_name if self.entity_name else 'All ' + entity_type}"
        )

    def _handle_error(self, error: Exception):
        """Handle errors during execution"""
        logger.error(f"Sync failed: {str(error)}", exc_info=True)
        self.log_data.error_message = str(error)
        self.log_data.status = Status.FAILED.value
        raise typer.Exit(code=1)

    def _finalize_logging(self):
        """Finalize logging and save command data"""
        self.log_data.execution_end = datetime.now()
        duration = (datetime.now() - self.start_time).total_seconds() * 1000
        self.log_data.duration_ms = duration
        logger.info(f"Total execution time: {duration:.2f} ms")

        with contextmanager(get_db)() as db:
            CommandLogsRepository(db).create_log(self.log_data.dict())
        logger.info(f"=== {self.command_name.replace('_', ' ').title()} completed ===")

    @staticmethod
    def save_command_log(log_data: CommandLog):
        """Save command log to database"""
        with contextmanager(get_db)() as db:
            CommandLogsRepository(db).create_log(log_data.dict())


class TeamSynchronizer(BaseSynchronizer):
    def __init__(self, team_name: Optional[str], dry_run: bool):
        super().__init__(team_name, dry_run, "sync_team")
        self.result = ResultTeams()

    def execute(self):
        """Main execution method for team synchronization"""
        try:
            self._log_start("teams")
            teams = self._get_target_teams()

            if not teams:
                return

            self._process_teams(teams)
            self._log_summary()
            self.log_data.status = Status.SUCCESS.value

        except Exception as e:
            self._handle_error(e)
        finally:
            self._finalize_logging()

    def _get_target_teams(self) -> list[dict]:
        """Retrieve and filter teams based on input parameters"""
        logger.info("Fetching list of teams...")
        teams = self.mm_client.get_invite_only_teams()

        if not teams:
            logger.warning("No private teams found!")
            return []

        if self.entity_name:
            teams = [team for team in teams if team.get("display_name") == self.entity_name]
            if not teams:
                error_msg = f"Team '{self.entity_name}' not found"
                logger.error(error_msg)
                raise Exception(error_msg)

        logger.info(f"Found {len(teams)} teams for processing")
        return teams

    def _process_teams(self, teams: list[dict]):
        """Process each team and synchronize members"""
        for team in teams:
            try:
                self._process_single_team(team)
            except Exception as e:
                team_name = team.get("display_name", "UNKNOWN")
                logger.error(f"Error processing team {team_name}: {str(e)}", exc_info=True)

    def _process_single_team(self, team: dict):
        """Process synchronization for a single team"""
        team_id = team["id"]
        team_name = team["display_name"]
        logger.info(f"Processing team: {team_name} (ID: {team_id})")

        if self.dry_run:
            self._dry_run_sync(team_id, team_name)
        else:
            self._live_sync(team_id)

        self.result.teams_processed += 1

    def _dry_run_sync(self, team_id: str, team_name: str):
        """Simulate synchronization in dry-run mode"""
        logger.info("Dry run mode - only analyzing changes")

        current_members = self.mm_client.get_team_members(team_id)
        current_member_ids = {m["user_id"] for m in current_members}
        logger.info(f"Current members: {len(current_member_ids)}")

        team_groups = client.get_team_id_by_groups(team_id)
        if not team_groups:
            logger.warning("No linked groups for this team - skipping")
            self.result.skipped_teams += 1
            return

        desired_users = self._get_desired_users(team_groups)
        to_add = desired_users - current_member_ids
        to_remove = current_member_ids - desired_users

        logger.info(f"Would add: {len(to_add)}")
        logger.info(f"Would remove: {len(to_remove)}")

        self.result.users_added += len(to_add)
        self.result.users_removed += len(to_remove)

    @staticmethod
    def _get_desired_users(team_groups: dict):
        """Get all users that should be in the team based on group membership"""
        desired_users = set()
        for group in team_groups.get("groups", []):
            group_members = client.get_group_members(group["id"])
            if group_members and "members" in group_members:
                desired_users.update({m["id"] for m in group_members["members"]})
        return desired_users

    def _live_sync(self, team_id: str):
        """Perform actual synchronization"""
        logger.info("Live synchronization mode")
        result = sync_group_users_to_team(team_id)
        sync_result = SyncResult(**result)

        logger.info(f"Added: {sync_result.users_added}")
        logger.info(f"Removed: {sync_result.users_removed}")

        self.result.users_added += sync_result.users_added
        self.result.users_removed += sync_result.users_removed

    def _log_summary(self):
        """Log summary statistics"""
        logger.info("=== Command summary teams ===")
        logger.info(f"  • Teams processed: {self.result.teams_processed}")
        logger.info(f"  • Skipped teams (no groups): {self.result.skipped_teams}")
        logger.info(f"  • Total users added: {self.result.users_added}")
        logger.info(f"  • Total users removed: {self.result.users_removed}")

        self.log_data.users_added = self.result.users_added
        self.log_data.users_removed = self.result.users_removed
        self.log_data.metrics = {
            "teams_processed": self.result.teams_processed,
            "skipped_teams": self.result.skipped_teams,
        }


class ChannelsSynchronizer(BaseSynchronizer):
    def __init__(self, channels: Optional[str], dry_run: bool):
        super().__init__(channels, dry_run, "sync-channels")
        self.result = ResultChannel()
        self.sync_manager = MattermostSyncManager(mattermost_client=self.mm_client)

    def execute(self):
        """Main execution method for channels synchronization"""
        try:
            self._log_start("channels")
            self.sync_channels(self.dry_run, self.entity_name)
            self._log_summary()
            self.log_data.status = Status.SUCCESS.value

        except Exception as e:
            self._handle_error(e)
        finally:
            self._finalize_logging()

    def sync_channels(
        self,
        dry_run: bool = False,
        channel_name: Optional[str] = None,
    ):
        """
        Synchronize Mattermost channel members with their team members and verify against AD.
        By default processes all channels, or can be limited to a specific channel.
        """
        params = SyncChannelsParams(dry_run=dry_run, channel_name=channel_name)
        logger.info(f"Starting sync-channels with params: {params}")

        try:
            logger.info("Fetching channels data...")
            channels_dict = get_channels_data(self.mm_client)

            if channel_name:
                channels_dict = self._filter_channels_by_name(channels_dict, channel_name)

            logger.info("Fetching user data (AD + Mattermost)...")
            ad_usernames, mm_user_map = get_user_data(self.sync_manager, self.mm_client)
            logger.info(
                f"User data loaded - AD users: {len(ad_usernames)}, Mattermost users: {len(mm_user_map)}"
            )

            result = self._process_channels(channels_dict, ad_usernames, mm_user_map, dry_run)

            self.result = result
            self._update_log_data(self.log_data, result)
            self.log_data.status = Status.SUCCESS.value

        except Exception as e:
            logger.error(f"Sync failed: {str(e)}", exc_info=True)
            self.log_data.status = Status.FAILED.value
            self.log_data.error_message = str(e)
            raise typer.Exit(1)

        logger.info("=== Channel synchronization completed ===")

    @staticmethod
    def _filter_channels_by_name(channels_dict: dict, channel_name: str) -> dict:
        """Filter channels by name and handle not found case"""
        filtered = {
            id: info
            for id, info in channels_dict.items()
            if info.get("display_name", "").lower() == channel_name.lower()
        }

        if not filtered:
            error_msg = f"Channel '{channel_name}' not found"
            logger.error(error_msg)
            raise Exception(error_msg)

        logger.info(f"Found channel: '{channel_name}' (ID: {list(filtered.keys())[0]})")
        return filtered

    def _process_channels(
        self, channels_dict: dict, ad_usernames: set, mm_user_map: dict, dry_run: bool
    ) -> ResultChannel:
        """Process all channels and return synchronization result"""
        result = ResultChannel(total_channels=len(channels_dict))

        logger.info(f"Starting processing of {result.total_channels} channels")

        for channel_id, channel_info in channels_dict.items():
            team_id = channel_info.get("team_id")
            if not team_id:
                logger.warning(
                    f"Channel '{channel_info.get('display_name')}' has no team_id - skipping"
                )
                continue

            logger.info(
                f"Processing channel: '{channel_info.get('display_name')}' "
                f"(ID: {channel_id}, Team ID: {team_id})"
            )

            if dry_run:
                added, removed = self._simulate_channel_sync(
                    channel_id, team_id, mm_user_map, ad_usernames
                )
            else:
                added, removed = process_channel(
                    self.mm_client, channel_id, channel_info, ad_usernames, mm_user_map
                )

            result.users_added += added
            result.users_removed += removed
            result.processed_channels += 1

            logger.info(
                f"Progress: {result.processed_channels}/{result.total_channels} channels processed"
            )

        return result

    def _simulate_channel_sync(
        self, channel_id: str, team_id: str, mm_user_map: dict, ad_usernames: set
    ) -> tuple:
        """Simulate channel synchronization without making changes"""
        logger.info("Dry run mode - checking changes without actual actions")
        current_members = self.mm_client.get_channel_members(channel_id)
        current_member_ids = {m["user_id"] for m in current_members}
        logger.info(f"Current members: {len(current_member_ids)}")

        team_members = self.mm_client.get_team_members(team_id)
        valid_member_ids = {
            member["user_id"]
            for member in team_members
            if mm_user_map.get(member["user_id"], "").lower() in ad_usernames
        }
        logger.info(f"Valid members (AD + channel): {len(valid_member_ids)}")

        to_add = valid_member_ids - current_member_ids
        to_remove = current_member_ids - valid_member_ids
        logger.info(f"Would add: {len(to_add)}")
        logger.info(f"Would remove: {len(to_remove)}")

        return len(to_add), len(to_remove)

    @staticmethod
    def _update_log_data(log_data: CommandLog, result: ResultChannel):
        """Update log data with synchronization results"""
        log_data.users_added = result.users_added
        log_data.users_removed = result.users_removed
        log_data.metrics = {
            "total_channels": result.total_channels,
            "processed_channels": result.processed_channels,
        }

    def _log_summary(self):
        """Log summary statistics"""
        logger.info("=== Command summary channel ===")
        logger.info(f"  • Channels processed: {self.result.processed_channels}")
        logger.info(f"  • Total channels: {self.result.total_channels}")
        logger.info(f"  • Total users added: {self.result.users_added}")
        logger.info(f"  • Total users removed: {self.result.users_removed}")

        self.log_data.users_added = self.result.users_added
        self.log_data.users_removed = self.result.users_removed
        self.log_data.metrics = {
            "total_channels": self.result.total_channels,
            "processed_channels": self.result.processed_channels,
        }
