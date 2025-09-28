from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.db.session import get_session
from app.repositories import tasks as tasks_repo
from app.schemas import TaskCollection, TaskCreate, TaskRead

router = APIRouter()


@router.get("/", response_model=TaskCollection)
def list_tasks(session: Session = Depends(get_session)) -> TaskCollection:
    items = tasks_repo.list_tasks(session)
    return TaskCollection(items=items)


@router.post("/", response_model=TaskRead, status_code=status.HTTP_201_CREATED)
def create_task(payload: TaskCreate, session: Session = Depends(get_session)) -> TaskRead:
    preferred_windows = (
        [window.model_dump() for window in payload.preferred_windows] if payload.preferred_windows else None
    )
    task = tasks_repo.create_task(
        session,
        title=payload.title,
        duration_minutes=payload.duration_minutes,
        earliest_start=payload.earliest_start,
        due=payload.due,
        priority=payload.priority,
        description=payload.description,
        preferred_windows=preferred_windows,
    )
    session.commit()
    session.refresh(task)
    return TaskRead.model_validate(task, from_attributes=True)


@router.get("/{task_id}", response_model=TaskRead)
def get_task(task_id: uuid.UUID, session: Session = Depends(get_session)) -> TaskRead:
    task = tasks_repo.get_task(session, task_id)
    if task is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
    return TaskRead.model_validate(task, from_attributes=True)


@router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
def delete_task(task_id: uuid.UUID, session: Session = Depends(get_session)) -> Response:
    task = tasks_repo.get_task(session, task_id)
    if task is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
    tasks_repo.delete_task(session, task_id)
    session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
