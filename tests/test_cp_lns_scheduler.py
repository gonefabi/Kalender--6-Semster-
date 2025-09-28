from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.scheduler.cp_lns import CPLNSScheduler, ScheduleMeeting, ScheduleRequest, ScheduleTask


def _ts(hour: int, minute: int = 0) -> datetime:
    return datetime(2025, 1, 6, hour, minute, tzinfo=timezone.utc)


def test_scheduler_respects_meetings_and_deadlines() -> None:
    scheduler = CPLNSScheduler(granularity_minutes=5, solver_time_limit_seconds=5.0)

    tasks = [
        ScheduleTask(
            task_id="task-a",
            duration_minutes=90,
            earliest_start=_ts(9),
            due=_ts(17),
            priority=5,
        ),
        ScheduleTask(
            task_id="task-b",
            duration_minutes=60,
            earliest_start=_ts(9),
            due=_ts(12),
            priority=10,
        ),
    ]
    meetings = [
        ScheduleMeeting(
            meeting_id="meeting-1",
            start=_ts(10),
            end=_ts(11),
        )
    ]

    request = ScheduleRequest(tasks=tasks, meetings=meetings)
    result = scheduler.schedule(request)

    assert result.unscheduled_tasks == []
    assert len(result.assignments) == 2

    assignment_map = {assignment.task_id: assignment for assignment in result.assignments}

    task_b = assignment_map["task-b"]
    assert task_b.end <= _ts(12)

    task_a = assignment_map["task-a"]
    assert task_a.start >= _ts(11)
    assert task_a.end <= _ts(17)

    # Ensure there is at least a 5 minute separation from the meeting.
    for assignment in result.assignments:
        assert not (_ts(10) <= assignment.start < _ts(11))

def test_scheduler_lns_respects_fixed_tasks() -> None:
    scheduler = CPLNSScheduler(granularity_minutes=5, solver_time_limit_seconds=5.0)

    tasks = [
        ScheduleTask(
            task_id="task-a",
            duration_minutes=60,
            earliest_start=_ts(9),
            due=_ts(17),
            priority=5,
        ),
        ScheduleTask(
            task_id="task-b",
            duration_minutes=60,
            earliest_start=_ts(9),
            due=_ts(17),
            priority=3,
        ),
    ]

    previous_assignments = {
        "task-a": (_ts(9), _ts(10)),
        "task-b": (_ts(10), _ts(11)),
    }

    # Meeting conflicts with task-b, but neighbourhood only allows task-b to move.
    meetings = [ScheduleMeeting(meeting_id="meeting-1", start=_ts(10), end=_ts(11))]

    request = ScheduleRequest(
        tasks=tasks,
        meetings=meetings,
        previous_assignments=previous_assignments,
        neighborhood_window=(_ts(9, 55), _ts(11, 5)),
    )

    result = scheduler.schedule(request)

    assignment_map = {assignment.task_id: assignment for assignment in result.assignments}
    assert assignment_map["task-a"].start == _ts(9)
    assert assignment_map["task-a"].end == _ts(10)
    assert assignment_map["task-b"].start >= _ts(11)
