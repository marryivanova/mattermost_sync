from typing import Optional

import typer

from config.settings import settings
from src.mattermost_cli.command.synchronizer import ChannelsSynchronizer, TeamSynchronizer
from src.mattermost_cli.mattermost.api_mattermost_sync.mattermost_client import MattermostClient

mm_client = MattermostClient(
    token=settings.MATTERMOST_TOKEN,
    url=settings.MATTERMOST_API,
    timeout=settings.TIMEOUT,
    max_retries=settings.MAX_RETRIES,
    retry_delay=settings.RETRY_DELAY,
)

app = typer.Typer(
    help="Tool for synchronizing users with Mattermost teams",
    epilog="Example: python sync_tool.py sync --team-name my-team",
)


@app.command()
def sync_channels(
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Run in simulation mode without making actual changes"
    ),
    channel_name: Optional[str] = typer.Option(
        None,
        "--channel-name",
        help="Name of a specific channel to synchronize (all channels if not specified)",
    ),
):
    tool = ChannelsSynchronizer(dry_run=dry_run, channels=channel_name)
    tool.execute()


@app.command()
def sync_team(
    team_name: Optional[str] = typer.Option(
        None,
        help="Name of the Mattermost team to synchronize (sync all teams if not specified)",
        show_default=False,
    ),
    dry_run: Optional[bool] = typer.Option(
        False, "--dry-run", help="Run in simulation mode without making actual changes"
    ),
):
    sync_tool = TeamSynchronizer(team_name, dry_run)
    sync_tool.execute()


if __name__ == "__main__":
    app()
