from __future__ import annotations

import random
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.db.initializer import create_database_schema
from app.db.session import SessionLocal
from app.repositories import tasks as tasks_repo


def seed_test_tasks(count: int = 10) -> None:
    durations = [random.randint(2, 6) * 60 for _ in range(count)]
    base_start = datetime.now(tz=timezone.utc).replace(hour=9, minute=0, second=0, microsecond=0)

    with SessionLocal() as session:  # type: Session
        for index, duration in enumerate(durations, start=1):
            start_time = base_start + timedelta(days=index // 3, hours=(index % 3) * 2)
            due_time = start_time + timedelta(minutes=duration + 120)
            title = f"Test {index}"
            tasks_repo.create_task(
                session,
                title=title,
                duration_minutes=duration,
                earliest_start=start_time,
                due=due_time,
                priority=random.randint(1, 5),
                description=f"Automatically seeded task {index}",
            )
        session.commit()


if __name__ == "__main__":
    create_database_schema()
    seed_test_tasks()
    print("Seeded 10 test tasks with random durations (2-6 hours).")
