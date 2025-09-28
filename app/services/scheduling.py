from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.repositories import meetings as meetings_repo
from app.repositories import plan_snapshots as snapshots_repo
from app.repositories import tasks as tasks_repo
from app.scheduler.cp_lns import (
    AssignedTask,
    CPLNSScheduler,
    ScheduleMeeting,
    ScheduleRequest,
    ScheduleResult,
    ScheduleTask,
)
from app.scheduler.swo import SWOScheduler
from app.scheduler.router import SchedulerType


@dataclass(slots=True)
class SchedulingMetrics:
    scheduled_count: int
    unscheduled_count: int
    total_deviation_minutes: int
    total_tardiness_minutes: int

    def to_dict(self) -> dict[str, int]:
        return {
            "scheduled_count": self.scheduled_count,
            "unscheduled_count": self.unscheduled_count,
            "total_deviation_minutes": self.total_deviation_minutes,
            "total_tardiness_minutes": self.total_tardiness_minutes,
        }


MAX_BLOCK_MINUTES = 120
MIN_BLOCK_MINUTES = 15


class SchedulingService:
    """Coordinates data retrieval, scheduling runs, and snapshot persistence."""

    def __init__(self, cp_scheduler: CPLNSScheduler, swo_scheduler: SWOScheduler | None = None) -> None:
        self.cp_scheduler = cp_scheduler
        self.swo_scheduler = swo_scheduler

    def run_cp_schedule(
        self,
        session: Session,
        *,
        label: str | None = None,
        neighborhood_window: tuple[datetime, datetime] | None = None,
    ) -> tuple[ScheduleResult, SchedulingMetrics]:
        return self._run_with_scheduler(
            session=session,
            scheduler=self.cp_scheduler,
            module=SchedulerType.CP_LNS.value,
            label=label,
            neighborhood_window=neighborhood_window,
        )

    def run_swo_schedule(
        self,
        session: Session,
        *,
        label: str | None = None,
    ) -> tuple[ScheduleResult, SchedulingMetrics]:
        if self.swo_scheduler is None:
            raise RuntimeError("SWO scheduler is not configured")
        return self._run_with_scheduler(
            session=session,
            scheduler=self.swo_scheduler,
            module=SchedulerType.SWO.value,
            label=label,
            neighborhood_window=None,
        )

    def _run_with_scheduler(
        self,
        *,
        session: Session,
        scheduler: object,
        module: str,
        label: str | None,
        neighborhood_window: tuple[datetime, datetime] | None,
    ) -> tuple[ScheduleResult, SchedulingMetrics]:
        tasks = tasks_repo.list_tasks(session)
        meetings = meetings_repo.list_meetings(session)

        previous_snapshot = snapshots_repo.get_latest_snapshot(session, module)
        previous_assignments_grouped = (
            snapshots_repo.assignments_as_mapping(previous_snapshot) if previous_snapshot else {}
        )

        expanded_tasks: list[ScheduleTask] = []
        schedule_mapping: dict[str, str] = {}
        segment_previous_assignments: dict[str, tuple[datetime, datetime]] = {}

        for task in tasks:
            preferred_windows = _extract_preferred_windows(task)
            segments = _segment_duration(task.duration_minutes)
            previous_segments = previous_assignments_grouped.get(str(task.id), [])

            for index, segment_duration in enumerate(segments):
                schedule_id = str(task.id) if index == 0 else f"{task.id}::seg{index+1}"
                expanded_tasks.append(
                    ScheduleTask(
                        task_id=schedule_id,
                        duration_minutes=segment_duration,
                        earliest_start=_as_utc(task.earliest_start),
                        due=_as_utc(task.due),
                        priority=task.priority,
                        preferred_windows=preferred_windows,
                    )
                )
                schedule_mapping[schedule_id] = str(task.id)
                if index < len(previous_segments):
                    prev_start, prev_end = previous_segments[index]
                    segment_previous_assignments[schedule_id] = (
                        _as_utc(prev_start),
                        _as_utc(prev_end),
                    )

        request = ScheduleRequest(
            tasks=expanded_tasks,
            meetings=[_to_schedule_meeting(meeting) for meeting in meetings],
            previous_assignments=segment_previous_assignments,
            neighborhood_window=neighborhood_window,
        )

        if not hasattr(scheduler, "schedule"):
            raise RuntimeError("Invalid scheduler provided")

        result = scheduler.schedule(request)
        remapped_result = _remap_schedule_result(result, schedule_mapping)

        metrics = _build_metrics(remapped_result)
        snapshots_repo.create_snapshot(
            session,
            module=module,
            label=label,
            assignments=remapped_result.assignments,
            metrics=metrics.to_dict(),
        )
        return remapped_result, metrics



def _as_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _to_schedule_meeting(meeting) -> ScheduleMeeting:
    return ScheduleMeeting(
        meeting_id=str(meeting.id),
        start=_as_utc(meeting.start_time),
        end=_as_utc(meeting.end_time),
    )


def _build_metrics(result: ScheduleResult) -> SchedulingMetrics:
    total_deviation = sum(assignment.deviation_minutes for assignment in result.assignments)
    total_tardiness = sum(assignment.tardiness_minutes for assignment in result.assignments)
    unscheduled_count = len(result.unscheduled_tasks)
    scheduled_count = len(result.assignments)
    return SchedulingMetrics(
        scheduled_count=scheduled_count,
        unscheduled_count=unscheduled_count,
        total_deviation_minutes=total_deviation,
        total_tardiness_minutes=total_tardiness,
    )


def _extract_preferred_windows(task) -> list[tuple[datetime, datetime]] | None:
    if not task.preferred_windows:
        return None
    windows: list[tuple[datetime, datetime]] = []
    for window in task.preferred_windows:
        start = datetime.fromisoformat(window["start"])
        end = datetime.fromisoformat(window["end"])
        windows.append((_as_utc(start), _as_utc(end)))
    return windows


def _segment_duration(total_minutes: int) -> list[int]:
    remaining = max(total_minutes, MIN_BLOCK_MINUTES)
    chunks: list[int] = []
    while remaining > 0:
        chunk = min(MAX_BLOCK_MINUTES, remaining)
        remainder = remaining - chunk
        if 0 < remainder < MIN_BLOCK_MINUTES:
            deficit = MIN_BLOCK_MINUTES - remainder
            adjustment = min(deficit, chunk - MIN_BLOCK_MINUTES)
            chunk -= adjustment
            remainder = remaining - chunk
        chunk = max(MIN_BLOCK_MINUTES, min(chunk, remaining))
        chunks.append(chunk)
        remaining -= chunk
    return chunks


def _remap_schedule_result(result: ScheduleResult, mapping: dict[str, str]) -> ScheduleResult:
    remapped_assignments: list[AssignedTask] = []
    for assignment in result.assignments:
        root_id = mapping.get(assignment.task_id, assignment.task_id)
        remapped_assignments.append(
            AssignedTask(
                task_id=root_id,
                start=assignment.start,
                end=assignment.end,
                deviation_minutes=assignment.deviation_minutes,
                tardiness_minutes=assignment.tardiness_minutes,
            )
        )

    remapped_unscheduled = sorted({mapping.get(task_id, task_id) for task_id in result.unscheduled_tasks})

    return ScheduleResult(
        assignments=remapped_assignments,
        unscheduled_tasks=remapped_unscheduled,
        objective_value=result.objective_value,
    )
