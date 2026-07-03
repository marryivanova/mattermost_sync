from sqlalchemy import Boolean, Column, DateTime, Float, Integer, String
from sqlalchemy.sql import func

from config.database import Base


class CommandExecutionLog(Base):
    __tablename__ = "command_logs"

    id = Column(Integer, primary_key=True, index=True)
    command_name = Column(String(255), nullable=False)
    team_name = Column(String(255))
    execution_start = Column(DateTime(timezone=True), nullable=False)
    execution_end = Column(DateTime(timezone=True))
    duration_ms = Column(Float)
    dry_run = Column(Boolean, default=False)
    status = Column(String(50), nullable=False)
    users_added = Column(Integer, default=0)
    users_removed = Column(Integer, default=0)
    error_message = Column(String)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
