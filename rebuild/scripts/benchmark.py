"""Measured local HTTP benchmark on disposable synthetic data, never the real database."""

import hashlib
import json
import math
import os
import platform
import re
import statistics
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from threading import Thread
from uuid import uuid4

import requests
from waitress import create_server

from demo_app.transport import post_json
from platform_app.database import get_db
from platform_app.models import Event
from scripts.lab import temporary_platform


def p95(values):
    return round(sorted(values)[math.ceil(0.95 * len(values)) - 1], 2)


def main():
    samples, errors = [], []
    root = Path(__file__).parents[1]
    with temporary_platform() as (app, app_id, _owner_id, key):
        now = datetime.now(UTC)

        def event(index, *, seeded=False):
            return {
                "schema_version": 1,
                "event_id": str(uuid4()),
                "occurred_at": (
                    now - timedelta(seconds=10000 - index) if seeded else datetime.now(UTC)
                ).isoformat(timespec="microseconds"),
                "event_type": "login",
                "outcome": "success",
                "subject_id": f"account-{index % 200}",
                "source_ip": "203.0.113.1",
                "session_id": str(uuid4()),
                "route": "/login",
                "response_duration_ms": 50.0,
                "interaction": None,
            }

        with app.app_context():
            database = get_db()
            records = []
            for index in range(10000):
                payload = event(index, seeded=True)
                records.append(
                    Event(
                        app_id=app_id,
                        event_id=payload["event_id"],
                        occurred_at=payload["occurred_at"],
                        subject_id=payload["subject_id"],
                        source_ip=payload["source_ip"],
                        session_id=payload["session_id"],
                        outcome=payload["outcome"],
                        response_duration_ms=50.0,
                        payload=payload,
                        payload_hash=hashlib.sha256(
                            json.dumps(payload, sort_keys=True).encode()
                        ).hexdigest(),
                    )
                )
            database.add_all(records)
            database.commit()
        server = create_server(app, host="127.0.0.1", port=0, threads=4)
        worker = Thread(target=server.run, daemon=True)
        worker.start()
        url = f"http://127.0.0.1:{server.effective_port}"
        try:
            started = time.perf_counter()
            # Five scheduled requests/second for 60 seconds. Serial overruns are
            # reported as lower achieved throughput, not concealed as a pass.
            for index in range(300):
                time.sleep(max(0, started + index / 5 - time.perf_counter()))
                tick = time.perf_counter()
                response = post_json(
                    url + "/api/v1/events",
                    json=event(index),
                    headers={"Authorization": f"Bearer {key}"},
                    timeout=30,
                    allow_redirects=False,
                )
                samples.append((time.perf_counter() - tick) * 1000)
                if response.status_code != 201:
                    errors.append(response.status_code)
            elapsed = time.perf_counter() - started
            with requests.Session() as browser:
                browser.trust_env = False
                login = browser.get(url + "/login", timeout=5)
                token = re.search(r'name="csrf_token" value="([^"]+)"', login.text).group(1)
                login = browser.post(
                    url + "/login",
                    data={
                        "csrf_token": token,
                        "login": "lab-owner",
                        "password": "lab-password-only",
                    },
                    timeout=5,
                )
                assert login.status_code == 200 and "Applications" in login.text
                dashboard = []
                for _ in range(30):
                    tick = time.perf_counter()
                    response = browser.get(f"{url}/applications/{app_id}/metrics", timeout=30)
                    dashboard.append((time.perf_counter() - tick) * 1000)
                    if response.status_code != 200:
                        errors.append(response.status_code)
            report = {
                "python": platform.python_version(),
                "os": platform.platform(),
                "cpu": platform.processor(),
                "logical_cpus": os.cpu_count(),
                "seed_events": 10000,
                "requests": 300,
                "scheduled_rate_per_second": 5,
                "elapsed_seconds": round(elapsed, 2),
                "achieved_rate": round(300 / elapsed, 2),
                "ingestion_p50_ms": round(statistics.median(samples), 2),
                "ingestion_p95_ms": p95(samples),
                "dashboard_samples": 30,
                "dashboard_p95_ms": p95(dashboard),
                "http_errors": errors,
                "ingestion_target_met": p95(samples) < 500,
                "dashboard_target_met": p95(dashboard) < 1000,
                "method": "Real Requests-to-Waitress HTTP; single SQLite process; "
                "10,000 successes sharing one IP; "
                "200 subjects; unique sessions; rate limiting disabled only in the disposable lab "
                "because the production 120/minute limit is below the 300/minute benchmark load.",
            }
        finally:
            server.task_dispatcher.shutdown()
            server.close()
            worker.join(timeout=2)
    (root / "reports").mkdir(exist_ok=True)
    (root / "reports" / "benchmark.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    lines = [
        "# Local performance benchmark",
        "",
        report["method"],
        "",
        f"Environment: {report['os']}; Python {report['python']}; "
        f"{report['cpu']}; {report['logical_cpus']} logical CPUs.",
        "",
        "| Measurement | Observed | Target |",
        "|---|---:|---:|",
        f"| Ingestion p95 | {report['ingestion_p95_ms']} ms | <500 ms |",
        f"| Dashboard p95 (30 requests) | {report['dashboard_p95_ms']} ms | <1000 ms |",
        f"| Achieved ingestion rate | {report['achieved_rate']} requests/s | 5 requests/s |",
        f"| HTTP failures | {len(errors)} | 0 |",
        "",
        "This measures a fixed benign workload, not attack-heavy worst-case capacity or an SLA. "
        "Browser polling adds up to five seconds to visible alert latency. "
        "Hardware contention changes results. "
        "Raw observations and target flags are in benchmark.json. No operator data was accessed.",
    ]
    (root / "reports" / "benchmark.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
