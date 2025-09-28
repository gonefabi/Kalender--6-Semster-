from __future__ import annotations

from datetime import datetime, timezone

import pytest


@pytest.mark.usefixtures("session_scope")
def test_scheduler_run_endpoint(client) -> None:
    created_tasks: list[dict] = []
    task_payloads = [
        {
            "title": "Deep work block",
            "duration_minutes": 120,
            "earliest_start": "2025-01-06T09:00:00+00:00",
            "due": "2025-01-06T17:00:00+00:00",
            "priority": 5,
        },
        {
            "title": "Prepare slides",
            "duration_minutes": 60,
            "earliest_start": "2025-01-06T09:00:00+00:00",
            "due": "2025-01-06T12:00:00+00:00",
            "priority": 8,
        },
    ]

    for payload in task_payloads:
        response = client.post("/api/v1/tasks/", json=payload)
        assert response.status_code == 201, response.text
        created_tasks.append(response.json())

    response = client.post(
        "/api/v1/meetings/",
        json={
            "title": "Team sync",
            "start_time": "2025-01-06T10:00:00+00:00",
            "end_time": "2025-01-06T11:00:00+00:00",
        },
    )
    assert response.status_code == 201, response.text

    response = client.post("/api/v1/scheduler/run", json={})
    assert response.status_code == 202, response.text

    result = response.json()
    assert result["scheduler"] == "CP_LNS"
    assert result["unscheduled_tasks"] == []
    assert result["runtime_ms"] >= 0

    assignments = result["assignments"]
    for task in created_tasks:
        assert any(item["task_id"] == task["id"] for item in assignments)

    high_priority_task = max(created_tasks, key=lambda item: item["priority"])
    high_assignment = next(item for item in assignments if item["task_id"] == high_priority_task["id"])
    assert datetime.fromisoformat(high_assignment["end"]) <= datetime(2025, 1, 6, 12, tzinfo=timezone.utc)


@pytest.mark.usefixtures("session_scope")
def test_scheduler_splits_long_task(client) -> None:
    response = client.post(
        "/api/v1/tasks/",
        json={
            "title": "Long research",
            "duration_minutes": 360,
            "earliest_start": "2025-01-06T09:00:00+00:00",
            "due": "2025-01-06T21:00:00+00:00",
            "priority": 3,
        },
    )
    assert response.status_code == 201, response.text
    task_id = response.json()["id"]

    response = client.post("/api/v1/scheduler/run", json={})
    assert response.status_code == 202, response.text
    result = response.json()

    task_assignments = [item for item in result["assignments"] if item["task_id"] == task_id]
    assert len(task_assignments) >= 3
    for assignment in task_assignments:
        start = datetime.fromisoformat(assignment["start"])
        end = datetime.fromisoformat(assignment["end"])
        duration = (end - start).total_seconds() / 60
        assert 15 <= duration <= 120


@pytest.mark.usefixtures("session_scope")
def test_swo_scheduler_produces_non_overlapping_blocks(client) -> None:
    task_payloads = [
        {
            "title": "SWO Task A",
            "duration_minutes": 360,
            "earliest_start": "2025-02-03T09:00:00+00:00",
            "due": "2025-02-07T17:00:00+00:00",
            "priority": 5,
        },
        {
            "title": "SWO Task B",
            "duration_minutes": 240,
            "earliest_start": "2025-02-03T09:00:00+00:00",
            "due": "2025-02-05T17:00:00+00:00",
            "priority": 4,
        },
    ]

    task_ids: list[str] = []
    for payload in task_payloads:
        response = client.post("/api/v1/tasks/", json=payload)
        assert response.status_code == 201, response.text
        task_ids.append(response.json()["id"])

    response = client.post(
        "/api/v1/meetings/",
        json={
            "title": "SWO Meeting",
            "start_time": "2025-02-03T12:00:00+00:00",
            "end_time": "2025-02-03T13:30:00+00:00",
        },
    )
    assert response.status_code == 201, response.text

    response = client.post("/api/v1/scheduler/run-swo", json={})
    assert response.status_code == 202, response.text
    result = response.json()

    assert result["scheduler"] == "SWO"
    assert result["runtime_ms"] >= 0
    assert result["unscheduled_tasks"] == []

    assignments = sorted(
        [
            (
                item["task_id"],
                datetime.fromisoformat(item["start"]),
                datetime.fromisoformat(item["end"]),
            )
            for item in result["assignments"]
        ],
        key=lambda entry: entry[1],
    )

    for i, (task_i, start_i, end_i) in enumerate(assignments):
        duration = (end_i - start_i).total_seconds() / 60
        assert 15 <= duration <= 120
        for task_j, start_j, end_j in assignments[i + 1 :]:
            if start_j >= end_i:
                break
            assert end_i <= start_j

    duration_by_task: dict[str, float] = {}
    for task_id, start, end in assignments:
        duration_by_task.setdefault(task_id, 0.0)
        duration_by_task[task_id] += (end - start).total_seconds() / 60

    expected = {
        task_ids[0]: task_payloads[0]["duration_minutes"],
        task_ids[1]: task_payloads[1]["duration_minutes"],
    }

    for task_id, expected_minutes in expected.items():
        assert pytest.approx(duration_by_task[task_id], 0.01) == expected_minutes
