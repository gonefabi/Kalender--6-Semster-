from __future__ import annotations

from datetime import datetime
from dataclasses import asdict
import time

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_session
from app.scheduler import CPLNSScheduler, SchedulerRouter, SchedulerType, SWOScheduler
from app.schemas import AssignmentRead, ScheduleRunRequest, ScheduleRunResponse
from app.services.scheduling import SchedulingService

router = APIRouter()

_cp_scheduler = CPLNSScheduler()
_swo_scheduler = SWOScheduler()
_scheduler_router = SchedulerRouter(cp_scheduler=_cp_scheduler, swo_scheduler=_swo_scheduler)
_scheduling_service = SchedulingService(cp_scheduler=_cp_scheduler, swo_scheduler=_swo_scheduler)


@router.post("/run", response_model=ScheduleRunResponse, status_code=status.HTTP_202_ACCEPTED)
def run_schedule(payload: ScheduleRunRequest, session: Session = Depends(get_session)) -> ScheduleRunResponse:
    active_scheduler = _scheduler_router.resolve()
    if not isinstance(active_scheduler, CPLNSScheduler):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Requested scheduler module is not available",
        )

    neighborhood_window: tuple[datetime, datetime] | None = None
    if payload.neighborhood_window:
        neighborhood_window = (payload.neighborhood_window.start, payload.neighborhood_window.end)

    start_time = time.perf_counter()
    result, metrics = _scheduling_service.run_cp_schedule(
        session,
        label=payload.label,
        neighborhood_window=neighborhood_window,
    )
    session.commit()
    runtime_ms = (time.perf_counter() - start_time) * 1000

    response = ScheduleRunResponse(
        scheduler=SchedulerType.CP_LNS.value,
        objective_value=result.objective_value,
        assignments=[AssignmentRead(**asdict(assignment)) for assignment in result.assignments],
        unscheduled_tasks=result.unscheduled_tasks,
        metrics=metrics.to_dict(),
        runtime_ms=runtime_ms,
    )
    return response


@router.post("/run-swo", response_model=ScheduleRunResponse, status_code=status.HTTP_202_ACCEPTED)
def run_swo_schedule(payload: ScheduleRunRequest, session: Session = Depends(get_session)) -> ScheduleRunResponse:
    start_time = time.perf_counter()

    try:
        result, metrics = _scheduling_service.run_swo_schedule(
            session,
            label=payload.label,
        )
    except RuntimeError as exc:  # pragma: no cover - guard for missing scheduler
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc

    session.commit()
    runtime_ms = (time.perf_counter() - start_time) * 1000

    response = ScheduleRunResponse(
        scheduler=SchedulerType.SWO.value,
        objective_value=result.objective_value,
        assignments=[AssignmentRead(**asdict(assignment)) for assignment in result.assignments],
        unscheduled_tasks=result.unscheduled_tasks,
        metrics=metrics.to_dict(),
        runtime_ms=runtime_ms,
    )
    return response
