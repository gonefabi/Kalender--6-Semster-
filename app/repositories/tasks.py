from __future__ import annotations

import uuid
from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import models


def list_tasks(session: Session) -> list[models.Task]:
    statement = select(models.Task).order_by(models.Task.earliest_start)
    return list(session.scalars(statement))


def get_task(session: Session, task_id: uuid.UUID) -> models.Task | None:
    return session.get(models.Task, task_id)


def get_tasks_by_ids(session: Session, task_ids: Sequence[uuid.UUID]) -> list[models.Task]:
    if not task_ids:
        return []
    statement = select(models.Task).where(models.Task.id.in_(task_ids))
    return list(session.scalars(statement))


def create_task(
    session: Session,
    *,
    title: str,
    duration_minutes: int,
    earliest_start,
    due,
    priority: int = 1,
    description: str | None = None,
    preferred_windows: list[dict] | None = None,
    metadata_payload: dict | None = None,
) -> models.Task:
    task = models.Task(
        title=title,
        duration_minutes=duration_minutes,
        earliest_start=earliest_start,
        due=due,
        priority=priority,
        description=description,
        preferred_windows=preferred_windows,
        metadata_payload=metadata_payload,
    )
    session.add(task)
    session.flush()
    return task


def delete_task(session: Session, task_id: uuid.UUID) -> None:
    task = session.get(models.Task, task_id)
    if task is None:
        return
    session.delete(task)
