import typing as t
from datetime import datetime
from enum import Enum

from pydantic import BaseModel


class Status(str, Enum):
    SUCCESS = "success"
    COMPLETED = "completed"
    FAILED = "failed"


class CommandLog(BaseModel):
    command_name: t.Optional[str] = None
    channel_name: t.Optional[str] = None
    team_name: t.Optional[str] = None
    execution_start: t.Optional[datetime] = None
    execution_end: t.Optional[datetime] = None
    duration_ms: t.Optional[float] = None
    status: t.Optional[t.Literal["success", "failed"]] = "success"
    error_message: t.Optional[str] = None
    users_added: t.Optional[int] = None
    users_removed: t.Optional[int] = None
    dry_run: t.Optional[bool] = False
    metrics: t.Optional[t.Dict[str, t.Any]] = None


class SyncResult(BaseModel):
    users_added: t.Optional[int] = 0
    users_removed: t.Optional[int] = 0
    current_count: t.Optional[int] = 0
    desired_count: t.Optional[int] = 0
    user_ids: t.Optional[t.Dict[str, t.Any]] = None


class MattermostTeam(BaseModel):
    id: str
    display_name: str
    name: str
    type: str


class MattermostUser(BaseModel):
    id: str
    username: str


class MattermostChannel(BaseModel):
    id: str
    team_id: str
    display_name: str
    name: str
    type: str


class SyncChannelsParams(BaseModel):
    dry_run: bool = False
    channel_name: t.Optional[str] = None


class SyncTeamParams(BaseModel):
    team_name: t.Optional[str] = None
    dry_run: bool = False


class RunInfo(BaseModel):
    start_time: str
    end_time: str
    duration: float
    success: bool
    error_message: t.Optional[str] = None
    users_added: int = 0
    users_removed: int = 0


class HistoryRecord(BaseModel):
    start_time: str
    execution_time: t.Optional[float] = None
    success: bool
    error_message: t.Optional[str] = None
    users_added: int = 0
    users_removed: int = 0


class StatsResponse(BaseModel):
    total_runs: int
    successful_runs: int
    failed_runs: int
    avg_duration: float
    total_users_added: int = 0
    total_users_removed: int = 0
    last_run: t.Optional[RunInfo] = None
    history: t.List[HistoryRecord] = []


class ResultChannel(BaseModel):
    total_channels: t.Optional[int] = 0
    processed_channels: t.Optional[int] = 0
    users_added: t.Optional[int] = 0
    users_removed: t.Optional[int] = 0


class ResultTeams(BaseModel):
    teams_processed: t.Optional[int] = 0
    users_added: t.Optional[int] = 0
    users_removed: t.Optional[int] = 0
    skipped_teams: t.Optional[int] = 0


class UserInfo(BaseModel):
    username: str
    name: str
    enabled: bool
    givenname: str
    userprincipalname: str
    user_id: t.Optional[str] = None


class GroupInfo(BaseModel):
    name: str
    dn: str
    member_count: int
    members: t.List[UserInfo]


# for MM sync
class Counters(BaseModel):
    added: int = 0
    removed: int = 0
