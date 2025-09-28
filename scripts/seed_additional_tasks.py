from __future__ import annotations

import random
from datetime import datetime, timedelta, timezone
from pathlib import Path
import sys

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.db.session import SessionLocal
from app.repositories.tasks import create_task


def seed_additional_tasks(count: int = 30) -> None:
    base_start = datetime(2025, 10, 6, 9, 0, tzinfo=timezone.utc)
    with SessionLocal() as session:
        for index in range(count):
            day_offset = index // 4
            start_time = base_start + timedelta(days=day_offset, hours=(index % 4) * 2)
            duration_hours = random.randint(2, 6)
            duration_minutes = duration_hours * 60
            due_time = start_time + timedelta(days=1, hours=duration_hours + 2)
            title = f"Additional Task {index + 1:02d}"
            create_task(
                session,
                title=title,
                duration_minutes=duration_minutes,
                earliest_start=start_time,
                due=due_time,
                priority=random.randint(1, 5),
                description=f"Auto-generated task {index + 1}",
            )
        session.commit()


if __name__ == "__main__":
    seed_additional_tasks()
