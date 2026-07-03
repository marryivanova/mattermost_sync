from typing import Any, Dict

from sqlalchemy.orm import Session

from db.models import CommandExecutionLog


class CommandLogsRepository:
    def __init__(self, db: Session):
        self.db = db

    def create_log(self, command_data: Dict[str, Any]) -> CommandExecutionLog:
        db_log = CommandExecutionLog(
            command_name=command_data.get("command_name"),
            team_name=command_data.get("team_name"),
            execution_start=command_data.get("execution_start"),
            execution_end=command_data.get("execution_end"),
            duration_ms=command_data.get("duration_ms"),
            dry_run=command_data.get("dry_run", False),
            status=command_data.get("status"),
            users_added=command_data.get("users_added", 0),
            users_removed=command_data.get("users_removed", 0),
            error_message=command_data.get("error_message"),
        )
        self.db.add(db_log)
        self.db.commit()
        self.db.refresh(db_log)
        return db_log
