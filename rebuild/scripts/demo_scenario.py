"""Send bounded synthetic events to a local platform; never target arbitrary websites."""

import os
import sys
import time
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import requests

from demo_app.transport import post_json


def main():
    key = os.environ.get("THREATWATCH_INGESTION_KEY")
    if not key:
        raise SystemExit("Set THREATWATCH_INGESTION_KEY before running this scenario.")
    session_id = str(uuid4())
    subject = f"scenario-{session_id[:8]}"
    started = datetime.now(UTC) - timedelta(seconds=30)
    for index in range(6):
        event = {
            "schema_version": 1,
            "event_id": str(uuid4()),
            "occurred_at": (started + timedelta(seconds=index)).isoformat(),
            "event_type": "login",
            "outcome": "failure" if index < 5 else "success",
            "subject_id": subject,
            "source_ip": "203.0.113.42",
            "session_id": session_id,
            "route": "/login",
            "response_duration_ms": 40.0 + index,
            "interaction": None,
        }
        try:
            response = post_json(
                "http://127.0.0.1:5000/api/v1/events",
                headers={"Authorization": f"Bearer {key}"},
                json=event,
                timeout=5,
                allow_redirects=False,
            )
        except requests.RequestException:
            raise SystemExit("Cannot reach the local platform on port 5000.") from None
        if response.status_code != 201:
            raise SystemExit(f"Event rejected with HTTP {response.status_code}; check setup.")
        print(f"Event {index + 1}: {event['outcome']} accepted")
        time.sleep(0.25)
    print(f"Open Alerts: expect AUTH-001 and AUTH-003 for {subject}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
