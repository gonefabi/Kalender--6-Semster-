from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Iterable

from .cp_lns import (
    AssignedTask,
    ScheduleMeeting,
    ScheduleRequest,
    ScheduleResult,
    ScheduleTask,
)


@dataclass(slots=True)
class _SegmentInfo:
    task: ScheduleTask
    duration_slots: int
    earliest_slot: int
    latest_start_slot: int
    due_slot: int
    previous_start_slot: int | None


class _TimeIndexer:
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


class SWOScheduler:
    """Squeaky Wheel Optimisation scheduler with greedy repair."""

    def __init__(
        self,
        *,
        granularity_minutes: int = 15,
        max_iterations: int = 6,
        unscheduled_penalty: int = 10_000,
        deviation_weight: int = 50,
        slack_weight: int = 5,
        working_day_start_hour: int = 9,
        working_day_end_hour: int = 17,
    ) -> None:
        if not (0 <= working_day_start_hour < working_day_end_hour <= 24):
            raise ValueError("working day hours must satisfy 0 <= start < end <= 24")
        self.granularity_minutes = granularity_minutes
        self.max_iterations = max_iterations
        self.unscheduled_penalty = unscheduled_penalty
        self.deviation_weight = deviation_weight
        self.slack_weight = slack_weight
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
        minute_offset = base_start.minute % self.granularity_minutes
        if minute_offset:
            base_start -= timedelta(minutes=minute_offset)

        indexer = _TimeIndexer(base=base_start, granularity_minutes=self.granularity_minutes)

        horizon_end_candidate = max(
            max((task.due for task in tasks), default=base_start),
            max((meeting.end for meeting in meetings), default=base_start),
        )
        horizon_slots = max(indexer.to_slot_ceiling(horizon_end_candidate) + 10, 10)

        segment_infos: dict[str, _SegmentInfo] = {}
        order: list[ScheduleTask] = []

        for task in tasks:
            duration_slots = indexer.duration_to_slots(task.duration_minutes)
            earliest_slot = indexer.to_slot_ceiling(task.earliest_start)
            due_slot = indexer.to_slot_ceiling(task.due)
            latest_start_slot = max(earliest_slot, min(due_slot - duration_slots, horizon_slots - duration_slots))

            previous_assignment = previous.get(task.task_id)
            previous_start_slot: int | None = None
            if previous_assignment:
                previous_start_slot = indexer.to_slot(previous_assignment[0])

            info = _SegmentInfo(
                task=task,
                duration_slots=duration_slots,
                earliest_slot=earliest_slot,
                latest_start_slot=latest_start_slot,
                due_slot=due_slot,
                previous_start_slot=previous_start_slot,
            )
            segment_infos[task.task_id] = info
            order.append(task)

        order.sort(key=lambda t: (-t.priority, t.earliest_start))

        base_occupancy = [False] * horizon_slots

        # Block outside working hours
        if self.working_day_start_hour > 0 or self.working_day_end_hour < 24:
            for slot in range(horizon_slots):
                dt = indexer.to_datetime(slot)
                hour = dt.hour + dt.minute / 60
                if hour < self.working_day_start_hour or hour >= self.working_day_end_hour:
                    base_occupancy[slot] = True

        # Block meetings
        for meeting in meetings:
            start_slot = max(0, indexer.to_slot(meeting.start))
            end_slot = min(horizon_slots, indexer.to_slot_ceiling(meeting.end))
            for slot in range(start_slot, end_slot):
                base_occupancy[slot] = True

        best_result: ScheduleResult | None = None
        best_unscheduled = math.inf
        best_objective = math.inf

        penalties: dict[str, float] = {task.task_id: 0.0 for task in tasks}

        for iteration in range(self.max_iterations):
            assignments, unscheduled = self._construct_schedule(order, segment_infos, base_occupancy, horizon_slots)
            result = self._build_result(assignments, unscheduled, segment_infos, indexer)

            objective = len(unscheduled) * self.unscheduled_penalty
            if best_result is None or len(unscheduled) < best_unscheduled or (
                len(unscheduled) == best_unscheduled and objective < best_objective
            ):
                best_result = result
                best_unscheduled = len(unscheduled)
                best_objective = objective

            new_penalties = self._evaluate_penalties(assignments, unscheduled, segment_infos)
            changed = any(abs(new_penalties[task.task_id] - penalties[task.task_id]) > 1e-6 for task in order)
            penalties = new_penalties

            new_order = sorted(
                order,
                key=lambda t: (
                    -penalties[t.task_id],
                    -t.priority,
                    t.earliest_start,
                ),
            )

            if not changed or new_order == order:
                break
            order = new_order

        if best_result is None:
            best_result = ScheduleResult(assignments=[], unscheduled_tasks=list(previous.keys()), objective_value=None)

        best_result.objective_value = best_objective if math.isfinite(best_objective) else None
        return best_result

    def _construct_schedule(
        self,
        order: list[ScheduleTask],
        segment_infos: dict[str, _SegmentInfo],
        base_occupancy: list[bool],
        horizon_slots: int,
    ) -> tuple[dict[str, int], list[str]]:
        occupancy = base_occupancy[:]
        assignments: dict[str, int] = {}
        unscheduled: list[str] = []

        for task in order:
            info = segment_infos[task.task_id]
            start_slot = self._find_slot(info, occupancy, horizon_slots)
            if start_slot is None:
                unscheduled.append(task.task_id)
                continue
            for slot in range(start_slot, start_slot + info.duration_slots):
                occupancy[slot] = True
            assignments[task.task_id] = start_slot

        return assignments, unscheduled

    def _find_slot(
        self,
        info: _SegmentInfo,
        occupancy: list[bool],
        horizon_slots: int,
    ) -> int | None:
        latest_start = min(info.latest_start_slot, horizon_slots - info.duration_slots)
        slot = info.earliest_slot
        while slot <= latest_start:
            end_slot = slot + info.duration_slots
            if end_slot > info.due_slot:
                slot += 1
                continue
            if all(not occupancy[idx] for idx in range(slot, end_slot)):
                return slot
            slot += 1
        return None

    def _build_result(
        self,
        assignments: dict[str, int],
        unscheduled: list[str],
        segment_infos: dict[str, _SegmentInfo],
        indexer: _TimeIndexer,
    ) -> ScheduleResult:
        assigned = []
        for task_id, start_slot in assignments.items():
            info = segment_infos[task_id]
            end_slot = start_slot + info.duration_slots
            start_dt = indexer.to_datetime(start_slot)
            end_dt = indexer.to_datetime(end_slot)

            deviation = 0
            if info.previous_start_slot is not None:
                deviation = abs(start_slot - info.previous_start_slot) * indexer.granularity

            tardiness = 0
            if end_dt > info.task.due:
                tardiness = int((end_dt - info.task.due).total_seconds() / 60)

            assigned.append(
                AssignedTask(
                    task_id=task_id,
                    start=start_dt,
                    end=end_dt,
                    deviation_minutes=deviation,
                    tardiness_minutes=tardiness,
                )
            )

        assigned.sort(key=lambda item: item.start)
        return ScheduleResult(assignments=assigned, unscheduled_tasks=unscheduled, objective_value=None)

    def _evaluate_penalties(
        self,
        assignments: dict[str, int],
        unscheduled: list[str],
        segment_infos: dict[str, _SegmentInfo],
    ) -> dict[str, float]:
        penalties: dict[str, float] = {}
        for task_id, info in segment_infos.items():
            if task_id in unscheduled:
                penalties[task_id] = float(self.unscheduled_penalty)
                continue

            start_slot = assignments[task_id]
            end_slot = start_slot + info.duration_slots
            slack = max(0, info.due_slot - end_slot)
            deviation_minutes = 0
            if info.previous_start_slot is not None:
                deviation_minutes = abs(start_slot - info.previous_start_slot) * self.granularity_minutes

            penalty = (
                self.deviation_weight * deviation_minutes
                + self.slack_weight * (1 / (slack + 1))
            )
            penalties[task_id] = penalty

        return penalties


__all__ = ["SWOScheduler"]
