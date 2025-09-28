from __future__ import annotations

import csv
from pathlib import Path
import sys
import os

import psutil

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from fastapi.testclient import TestClient

from app.main import create_app

ITERATIONS = 1000
CP_OUTPUT = Path("benchmarks_cp_lns.csv")
SWO_OUTPUT = Path("benchmarks_swo.csv")


def run_benchmark(
    *,
    iterations: int,
    filename: Path,
    endpoint: str,
    client: TestClient,
) -> None:
    process = psutil.Process(os.getpid())
    rows: list[tuple[int, float, float, float, float]] = []
    for run_id in range(1, iterations + 1):
        cpu_before = process.cpu_times()
        rss_before, vms_before = process.memory_info().rss, process.memory_info().vms

        response = client.post(endpoint, json={})
        response.raise_for_status()
        data = response.json()

        cpu_after = process.cpu_times()
        mem_info = process.memory_info()

        runtime_ms = float(data.get("runtime_ms", 0.0))
        cpu_time_ms = (
            (cpu_after.user + cpu_after.system)
            - (cpu_before.user + cpu_before.system)
        ) * 1000.0
        rss_mb = mem_info.rss / (1024 * 1024)
        vms_mb = mem_info.vms / (1024 * 1024)

        rows.append((run_id, runtime_ms, cpu_time_ms, rss_mb, vms_mb))

    with filename.open("w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["run_id", "runtime_ms", "cpu_time_ms", "rss_mb", "vms_mb"])
        writer.writerows(rows)


def main() -> None:
    app = create_app()
    client = TestClient(app)

    run_benchmark(
        iterations=ITERATIONS,
        filename=CP_OUTPUT,
        endpoint="/api/v1/scheduler/run",
        client=client,
    )

    run_benchmark(
        iterations=ITERATIONS,
        filename=SWO_OUTPUT,
        endpoint="/api/v1/scheduler/run-swo",
        client=client,
    )

    print(f"CP+LNS benchmark written to {CP_OUTPUT}")
    print(f"SWO benchmark written to {SWO_OUTPUT}")


if __name__ == "__main__":
    main()
