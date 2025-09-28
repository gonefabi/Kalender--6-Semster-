from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import models
from app.scheduler.cp_lns import AssignedTask


def get_latest_snapshot(session: Session, module: str) -> models.PlanSnapshot | None:
    statement = (
        select(models.PlanSnapshot)
        .where(models.PlanSnapshot.module == module)
        .order_by(models.PlanSnapshot.created_at.desc())
        .limit(1)
    )
    return session.scalars(statement).first()


def create_snapshot(
    session: Session,
    *,
    module: str,
    label: str | None,
    assignments: list[AssignedTask],
    metrics: dict | None = None,
) -> models.PlanSnapshot:
    snapshot = models.PlanSnapshot(module=module, label=label, metrics=metrics or {})
    session.add(snapshot)
    session.flush()

    for assignment in assignments:
        task_assignment = models.TaskAssignment(
            plan_snapshot_id=snapshot.id,
            task_id=uuid.UUID(assignment.task_id),
            scheduled_start=assignment.start,
            scheduled_end=assignment.end,
            deviation_minutes=assignment.deviation_minutes,
            tardiness_minutes=assignment.tardiness_minutes,
            cost_components=None,
        )
        session.add(task_assignment)
    session.flush()
    return snapshot


def assignments_as_mapping(snapshot: models.PlanSnapshot) -> dict[str, list[tuple[datetime, datetime]]]:
    grouped: dict[str, list[tuple[datetime, datetime]]] = {}
    for assignment in snapshot.assignments:
        grouped.setdefault(str(assignment.task_id), []).append(
            (assignment.scheduled_start, assignment.scheduled_end)
        )
    for assignments in grouped.values():
        assignments.sort(key=lambda item: item[0])
    return grouped
