from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import models


def list_meetings(session: Session) -> list[models.Meeting]:
    statement = select(models.Meeting).order_by(models.Meeting.start_time)
    return list(session.scalars(statement))


def create_meeting(
    session: Session,
    *,
    title: str,
    start_time,
    end_time,
    metadata_payload: dict | None = None,
) -> models.Meeting:
    meeting = models.Meeting(
        title=title,
        start_time=start_time,
        end_time=end_time,
        metadata_payload=metadata_payload,
    )
    session.add(meeting)
    session.flush()
    return meeting


def delete_meeting(session: Session, meeting_id: uuid.UUID) -> None:
    meeting = session.get(models.Meeting, meeting_id)
    if meeting is None:
        return
    session.delete(meeting)


def create_or_update_external_meeting(
    session: Session,
    *,
    external_id: str,
    title: str,
    start_time,
    end_time,
    source: str,
    metadata_payload: dict | None = None,
) -> models.Meeting:
    statement = select(models.Meeting).where(models.Meeting.external_id == external_id)
    meeting = session.scalars(statement).first()
    if meeting is None:
        meeting = models.Meeting(
            title=title,
            start_time=start_time,
            end_time=end_time,
            external_id=external_id,
            source=source,
            metadata_payload=metadata_payload,
        )
        session.add(meeting)
    else:
        meeting.title = title
        meeting.start_time = start_time
        meeting.end_time = end_time
        meeting.metadata_payload = metadata_payload
        meeting.source = source
        session.add(meeting)
    session.flush()
    return meeting


def update_meeting_from_event(
    session: Session,
    meeting: models.Meeting,
    *,
    title,
    start_time,
    end_time,
    metadata: dict | None,
) -> models.Meeting:
    meeting.title = title
    meeting.start_time = start_time
    meeting.end_time = end_time
    meeting.metadata_payload = metadata
    session.add(meeting)
    session.flush()
    return meeting
