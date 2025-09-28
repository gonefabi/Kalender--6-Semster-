from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin


class Task(Base, TimestampMixin):
    """Flexible work item that needs to be scheduled."""

    __tablename__ = "tasks"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(String, nullable=True)
    duration_minutes: Mapped[int] = mapped_column(nullable=False)
    earliest_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    due: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    priority: Mapped[int] = mapped_column(nullable=False, default=1)
    preferred_windows: Mapped[list[dict] | None] = mapped_column(JSONB, nullable=True)
    metadata_payload: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    assignments: Mapped[list[TaskAssignment]] = relationship(back_populates="task", cascade="all, delete-orphan")


class Meeting(Base, TimestampMixin):
    """Fixed calendar event blocking time on the resource."""

    __tablename__ = "meetings"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    start_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    end_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    external_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    source: Mapped[str | None] = mapped_column(String(64), nullable=True)
    metadata_payload: Mapped[dict | None] = mapped_column(JSONB, nullable=True)


class PlanSnapshot(Base, TimestampMixin):
    """Stores the latest schedule assignments for a module."""

    __tablename__ = "plan_snapshots"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    module: Mapped[str] = mapped_column(String(32), nullable=False)
    label: Mapped[str | None] = mapped_column(String(255), nullable=True)
    assignments: Mapped[list[TaskAssignment]] = relationship(back_populates="plan", cascade="all, delete-orphan")
    metrics: Mapped[dict | None] = mapped_column(JSONB, nullable=True)


class TaskAssignment(Base, TimestampMixin):
    """Assignment of a task within a plan snapshot."""

    __tablename__ = "task_assignments"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    plan_snapshot_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("plan_snapshots.id", ondelete="CASCADE"), nullable=False)
    task_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False)
    scheduled_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    scheduled_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    deviation_minutes: Mapped[int] = mapped_column(nullable=False, default=0)
    tardiness_minutes: Mapped[int] = mapped_column(nullable=False, default=0)
    cost_components: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    plan: Mapped[PlanSnapshot] = relationship(back_populates="assignments")
    task: Mapped[Task] = relationship(back_populates="assignments")


class IntegrationCredential(Base, TimestampMixin):
    """Stores OAuth credentials for external integrations (e.g., Google)."""

    __tablename__ = "integration_credentials"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    provider: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    account_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    calendar_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    access_token: Mapped[str | None] = mapped_column(String, nullable=True)
    refresh_token: Mapped[str | None] = mapped_column(String, nullable=True)
    token_expiry: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    scopes: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
