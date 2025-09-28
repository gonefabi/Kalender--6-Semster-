from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.db import models
from app.db.session import get_session
from app.repositories import meetings as meetings_repo
from app.schemas import MeetingCollection, MeetingCreate, MeetingRead

router = APIRouter()


@router.get("/", response_model=MeetingCollection)
def list_meetings(session: Session = Depends(get_session)) -> MeetingCollection:
    items = meetings_repo.list_meetings(session)
    return MeetingCollection(items=items)


@router.post("/", response_model=MeetingRead, status_code=status.HTTP_201_CREATED)
def create_meeting(payload: MeetingCreate, session: Session = Depends(get_session)) -> MeetingRead:
    meeting = meetings_repo.create_meeting(
        session,
        title=payload.title,
        start_time=payload.start_time,
        end_time=payload.end_time,
        metadata_payload=payload.metadata_payload,
    )
    session.commit()
    session.refresh(meeting)
    return MeetingRead.model_validate(meeting, from_attributes=True)


@router.delete("/{meeting_id}", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
def delete_meeting(meeting_id: uuid.UUID, session: Session = Depends(get_session)) -> Response:
    meeting = session.get(models.Meeting, meeting_id)
    if meeting is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Meeting not found")
    meetings_repo.delete_meeting(session, meeting_id)
    session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
