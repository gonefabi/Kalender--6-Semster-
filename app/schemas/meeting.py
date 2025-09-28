from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class MeetingBase(BaseModel):
    title: str
    start_time: datetime
    end_time: datetime
    metadata_payload: dict | None = None


class MeetingCreate(MeetingBase):
    pass


class MeetingRead(MeetingBase):
    id: UUID
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class MeetingCollection(BaseModel):
    items: list[MeetingRead]
