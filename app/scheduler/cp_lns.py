from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Iterable

from ortools.sat.python import cp_model


@dataclass(slots=True)
class ScheduleTask:
    task_id: str
    duration_minutes: int
    earliest_start: datetime
    due: datetime
    priority: int
    preferred_windows: list[tuple[datetime, datetime]] | None = None
    fixed_start: datetime | None = None


@dataclass(slots=True)
class ScheduleMeeting:
    meeting_id: str
    start: datetime
    end: datetime


@dataclass(slots=True)
class ScheduleRequest:
    tasks: list[ScheduleTask]
    meetings: list[ScheduleMeeting]
    previous_assignments: dict[str, tuple[datetime, datetime]] | None = None
    neighborhood_window: tuple[datetime, datetime] | None = None


@dataclass(slots=True)
class AssignedTask:
    task_id: str
    start: datetime
    end: datetime
    deviation_minutes: int
    tardiness_minutes: int


@dataclass(slots=True)
class ScheduleResult:
    assignments: list[AssignedTask]
    unscheduled_tasks: list[str]
    objective_value: int | None


class _TimeIndexer:
    """Utility to convert datetimes into discrete solver slots."""

    def __init__(self, base: datetime, granularity_minutes: int) -> None:
        self.base = base
        self.granularity = granularity_minutes

    def to_slot(self, timestamp: datetime) -> int:
        delta = timestamp - self.base
        minutes = delta.total_seconds() / 60
        return int(math.floor(minutes / self.granularity))

    def to_slot_ceiling(self, timestamp: datetime) -> int:
        delta = timestamp - self.base
        minutes = delta.total_seconds() / 60
        return int(math.ceil(minutes / self.granularity))

    def to_datetime(self, slot: int) -> datetime:
        return self.base + timedelta(minutes=slot * self.granularity)

    def duration_to_slots(self, minutes: int) -> int:
        return max(1, math.ceil(minutes / self.granularity))


class CPLNSScheduler:
    """Constraint Programming + Large Neighbourhood Search scheduler."""

    def __init__(
        self,
        *,
        granularity_minutes: int = 5,
        solver_time_limit_seconds: float = 15.0,
        search_workers: int | None = None,
        tardiness_weight: int = 200,
        stability_weight: int = 30,
        start_time_weight: int = 1,
        unscheduled_weight: int = 10_000,
        working_day_start_hour: int = 9,
        working_day_end_hour: int = 17,
    ) -> None:
        self.granularity_minutes = granularity_minutes
        self.solver_time_limit_seconds = solver_time_limit_seconds
        self.search_workers = search_workers
        self.tardiness_weight = tardiness_weight
        self.stability_weight = stability_weight
        self.start_time_weight = start_time_weight
        self.unscheduled_weight = unscheduled_weight
        if not (0 <= working_day_start_hour < working_day_end_hour <= 24):
            raise ValueError("working day hours must satisfy 0 <= start < end <= 24")
        self.working_day_start_hour = working_day_start_hour
        self.working_day_end_hour = working_day_end_hour

    def schedule(self, request: ScheduleRequest) -> ScheduleResult:
        if not request.tasks:
            return ScheduleResult(assignments=[], unscheduled_tasks=[], objective_value=0)

        tasks = request.tasks
        meetings = request.meetings
        previous = request.previous_assignments or {}

        base_start_candidates: Iterable[datetime] = [task.earliest_start for task in tasks]
        if meetings:
            base_start_candidates = list(base_start_candidates) + [meeting.start for meeting in meetings]
        base_start = min(base_start_candidates)
        base_start = base_start.replace(second=0, microsecond=0)
        # Align minutes to the granularity grid.
        minute_offset = base_start.minute % self.granularity_minutes
        if minute_offset:
            base_start -= timedelta(minutes=minute_offset)

        indexer = _TimeIndexer(base=base_start, granularity_minutes=self.granularity_minutes)

        horizon_end_candidate = max(
            max((task.due for task in tasks), default=base_start),
            max((meeting.end for meeting in meetings), default=base_start),
        )
        horizon_slots = max(indexer.to_slot_ceiling(horizon_end_candidate) + 10, 10)

        model = cp_model.CpModel()

        intervals: list[cp_model.IntervalVar] = []
        start_vars: dict[str, cp_model.IntVar] = {}
        end_vars: dict[str, cp_model.IntVar] = {}
        present_vars: dict[str, cp_model.BoolVar] = {}
        lateness_vars: dict[str, cp_model.IntVar] = {}
        deviation_vars: dict[str, cp_model.IntVar] = {}

        neighborhood = request.neighborhood_window
        window_slot_range: tuple[int, int] | None = None
        if neighborhood is not None:
            window_slot_range = (
                indexer.to_slot(neighborhood[0]),
                indexer.to_slot_ceiling(neighborhood[1]),
            )

        for task in tasks:
            duration_slots = indexer.duration_to_slots(task.duration_minutes)
            earliest_slot = indexer.to_slot(task.earliest_start)
            latest_start_slot = indexer.to_slot_ceiling(task.due) - duration_slots
            latest_start_slot = min(latest_start_slot, horizon_slots - duration_slots)
            earliest_slot = max(0, earliest_slot)
            latest_start_slot = max(earliest_slot, latest_start_slot)

            start = model.NewIntVar(earliest_slot, latest_start_slot, f"start_{task.task_id}")
            end = model.NewIntVar(earliest_slot + duration_slots, horizon_slots, f"end_{task.task_id}")
            presence = model.NewBoolVar(f"present_{task.task_id}")
            interval = model.NewOptionalIntervalVar(start, duration_slots, end, presence, f"interval_{task.task_id}")

            start_vars[task.task_id] = start
            end_vars[task.task_id] = end
            present_vars[task.task_id] = presence
            intervals.append(interval)

            # Respect earliest start / due windows when task is scheduled.
            model.Add(start >= earliest_slot).OnlyEnforceIf(presence)
            model.Add(end <= indexer.to_slot_ceiling(task.due)).OnlyEnforceIf(presence)

            previous_assignment = previous.get(task.task_id)
            previous_start_slot: int | None = None
            if previous_assignment:
                previous_start_slot = indexer.to_slot(previous_assignment[0])

            if task.fixed_start is not None:
                fixed_slot = indexer.to_slot(task.fixed_start)
                model.Add(start == fixed_slot)
                model.Add(presence == 1)
                previous_start_slot = fixed_slot
            elif window_slot_range and previous_start_slot is not None:
                if not (window_slot_range[0] <= previous_start_slot <= window_slot_range[1]):
                    # Keep the task fixed outside of the neighbourhood.
                    model.Add(start == previous_start_slot)
                    model.Add(presence == 1)

            # Tasks without any previous assignment should be scheduled.
            if previous_assignment is None and task.fixed_start is None:
                model.Add(presence == 1)

            # Lateness variables capture deadline violation (0 if on-time).
            tardiness = model.NewIntVar(0, horizon_slots, f"late_{task.task_id}")
            model.Add(tardiness >= end - indexer.to_slot_ceiling(task.due)).OnlyEnforceIf(presence)
            model.Add(tardiness == 0).OnlyEnforceIf(presence.Not())
            lateness_vars[task.task_id] = tardiness

            deviation = model.NewIntVar(0, horizon_slots, f"dev_{task.task_id}")
            if previous_start_slot is not None:
                model.Add(deviation >= start - previous_start_slot)
                model.Add(deviation >= previous_start_slot - start)
            else:
                model.Add(deviation == 0)
            deviation_vars[task.task_id] = deviation

        # Fixed meetings become immutable intervals in the NoOverlap constraint.
        for meeting in meetings:
            meeting_start_slot = indexer.to_slot(meeting.start)
            meeting_duration_minutes = max(1, math.ceil((meeting.end - meeting.start).total_seconds() / 60))
            meeting_duration_slots = indexer.duration_to_slots(meeting_duration_minutes)
            start_fixed = model.NewIntVar(meeting_start_slot, meeting_start_slot, f"meeting_start_{meeting.meeting_id}")
            end_fixed = model.NewIntVar(
                meeting_start_slot + meeting_duration_slots,
                meeting_start_slot + meeting_duration_slots,
                f"meeting_end_{meeting.meeting_id}",
            )
            meeting_interval = model.NewIntervalVar(
                start_fixed, meeting_duration_slots, end_fixed, f"meeting_{meeting.meeting_id}"
            )
            intervals.append(meeting_interval)

        def add_block_interval(start_dt: datetime, end_dt: datetime) -> None:
            start_slot = max(0, indexer.to_slot(start_dt))
            end_slot = min(horizon_slots, indexer.to_slot_ceiling(end_dt))
            if end_slot <= start_slot:
                return
            duration = end_slot - start_slot
            start_fixed = model.NewIntVar(start_slot, start_slot, f"block_start_{len(intervals)}")
            end_fixed = model.NewIntVar(
                start_slot + duration,
                start_slot + duration,
                f"block_end_{len(intervals)}",
            )
            block_interval = model.NewIntervalVar(
                start_fixed,
                duration,
                end_fixed,
                f"block_{len(intervals)}",
            )
            intervals.append(block_interval)

        working_start_hour = self.working_day_start_hour
        working_end_hour = self.working_day_end_hour
        if working_start_hour > 0 or working_end_hour < 24:
            horizon_end_dt = indexer.to_datetime(horizon_slots)
            current_day = base_start.replace(hour=0, minute=0, second=0, microsecond=0)
            if current_day > base_start:
                current_day -= timedelta(days=1)
            while current_day < horizon_end_dt:
                work_start_dt = current_day.replace(
                    hour=working_start_hour, minute=0, second=0, microsecond=0
                )
                work_end_dt = current_day.replace(
                    hour=working_end_hour, minute=0, second=0, microsecond=0
                )
                next_day_dt = current_day + timedelta(days=1)
                add_block_interval(current_day, work_start_dt)
                add_block_interval(work_end_dt, next_day_dt)
                current_day = next_day_dt

        model.AddNoOverlap(intervals)

        objective_terms: list[cp_model.LinearExpr] = []
        for task in tasks:
            presence = present_vars[task.task_id]
            tardiness = lateness_vars[task.task_id]
            deviation = deviation_vars[task.task_id]
            start = start_vars[task.task_id]

            # Encourage assignments to exist.
            objective_terms.append(self.unscheduled_weight * (1 - presence))
            # Penalise lateness with priority weight.
            objective_terms.append(self.tardiness_weight * task.priority * tardiness)
            # Encourage stability by penalising deviation from prior plan.
            objective_terms.append(self.stability_weight * deviation)
            # Secondary objective to keep earlier tasks earlier when otherwise equal.
            objective_terms.append(self.start_time_weight * task.priority * start)

        model.Minimize(cp_model.LinearExpr.Sum(objective_terms))

        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = self.solver_time_limit_seconds
        if self.search_workers is not None:
            solver.parameters.num_search_workers = self.search_workers

        status = solver.Solve(model)

        assignments: list[AssignedTask] = []
        unscheduled: list[str] = []

        if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            unscheduled = [task.task_id for task in tasks]
            return ScheduleResult(assignments=[], unscheduled_tasks=unscheduled, objective_value=None)

        for task in tasks:
            presence_val = solver.Value(present_vars[task.task_id])
            if presence_val == 0:
                unscheduled.append(task.task_id)
                continue

            start_slot = solver.Value(start_vars[task.task_id])
            end_slot = solver.Value(end_vars[task.task_id])
            start_dt = indexer.to_datetime(start_slot)
            end_dt = indexer.to_datetime(end_slot)

            deviation_minutes = solver.Value(deviation_vars[task.task_id]) * self.granularity_minutes
            tardiness_minutes = solver.Value(lateness_vars[task.task_id]) * self.granularity_minutes

            assignments.append(
                AssignedTask(
                    task_id=task.task_id,
                    start=start_dt,
                    end=end_dt,
                    deviation_minutes=deviation_minutes,
                    tardiness_minutes=tardiness_minutes,
                )
            )

        objective_value = int(solver.ObjectiveValue()) if status == cp_model.OPTIMAL else None
        assignments.sort(key=lambda x: x.start)
        return ScheduleResult(assignments=assignments, unscheduled_tasks=unscheduled, objective_value=objective_value)
