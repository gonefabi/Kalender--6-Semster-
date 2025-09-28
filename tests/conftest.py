from __future__ import annotations

import os
import subprocess
import time
from collections.abc import Generator

import psycopg
from sqlalchemy import text
import pytest
from fastapi.testclient import TestClient

os.environ["APP_ENV"] = "test"
os.environ["SCHEDULER_MODULE"] = "CP_LNS"
INSIDE_DOCKER = os.getenv("INSIDE_DOCKER") == "1"
DB_HOST = os.getenv("TEST_DB_HOST", "db" if INSIDE_DOCKER else "localhost")
DOCKER_COMPOSE_CMD = os.getenv("DOCKER_COMPOSE_CMD", "docker-compose")
os.environ["DATABASE_URL"] = f"postgresql+psycopg://calendar_user:calendar_pass@{DB_HOST}:5432/calendar_test"

from app.db.initializer import create_database_schema  # noqa: E402
from app.db.session import SessionLocal, engine  # noqa: E402
from app.main import create_app  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def ensure_postgres_service() -> Generator[None, None, None]:
    if INSIDE_DOCKER:
        _wait_for_postgres(host=DB_HOST)
        yield
    else:
        subprocess.run([DOCKER_COMPOSE_CMD, "up", "-d", "db"], check=True)
        _wait_for_postgres(host=DB_HOST)
        try:
            yield
        finally:
            subprocess.run([DOCKER_COMPOSE_CMD, "stop", "db"], check=True)


@pytest.fixture(scope="session", autouse=True)
def create_test_database() -> None:
    connection = psycopg.connect(f"postgresql://calendar_user:calendar_pass@{DB_HOST}:5432/postgres")
    connection.autocommit = True
    with connection:
        with connection.cursor() as cursor:
            cursor.execute("DROP DATABASE IF EXISTS calendar_test")
            cursor.execute("CREATE DATABASE calendar_test")
    connection.close()
    engine.dispose()
    create_database_schema()


@pytest.fixture()
def session_scope() -> Generator:
    session = SessionLocal()
    try:
        yield session
        session.commit()
        session.execute(text("TRUNCATE task_assignments, plan_snapshots, meetings, tasks, integration_credentials RESTART IDENTITY CASCADE"))
        session.commit()
    finally:
        session.close()


@pytest.fixture()
def client() -> Generator[TestClient, None, None]:
    app = create_app()
    with TestClient(app) as test_client:
        yield test_client


def _wait_for_postgres(timeout: float = 15.0, host: str = "localhost") -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with psycopg.connect(f"postgresql://calendar_user:calendar_pass@{host}:5432/postgres"):
                return
        except psycopg.OperationalError:
            time.sleep(0.5)
    raise RuntimeError("PostgreSQL service did not become available")
