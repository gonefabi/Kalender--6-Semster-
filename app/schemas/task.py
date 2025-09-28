from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


class PreferredWindow(BaseModel):
    start: datetime
    end: datetime
    weight: int | None = Field(default=None, ge=1, le=100)


class TaskBase(BaseModel):
    title: str
    duration_minutes: int = Field(gt=0)
    earliest_start: datetime
    due: datetime
    priority: int = Field(default=1, ge=1, le=10)
    description: str | None = None
    preferred_windows: list[PreferredWindow] | None = None


class TaskCreate(TaskBase):
    pass


class TaskUpdate(BaseModel):
    title: str | None = None
    duration_minutes: int | None = Field(default=None, gt=0)
    earliest_start: datetime | None = None
    due: datetime | None = None
    priority: int | None = Field(default=None, ge=1, le=10)
    description: str | None = None
    preferred_windows: list[PreferredWindow] | None = None


class TaskRead(TaskBase):
    id: UUID
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class TaskCollection(BaseModel):
    items: list[TaskRead]
