from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class NeighborhoodWindow(BaseModel):
    start: datetime
    end: datetime


class ScheduleRunRequest(BaseModel):
    label: str | None = None
    neighborhood_window: NeighborhoodWindow | None = None


class AssignmentRead(BaseModel):
    task_id: str
    start: datetime
    end: datetime
    deviation_minutes: int
    tardiness_minutes: int


class ScheduleRunResponse(BaseModel):
    scheduler: str
    objective_value: int | None
    assignments: list[AssignmentRead]
    unscheduled_tasks: list[str]
    metrics: dict
    runtime_ms: float | None = None
