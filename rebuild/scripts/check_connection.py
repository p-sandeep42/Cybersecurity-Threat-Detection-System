"""Diagnose demo configuration without storing events or printing credentials."""

import os
import re
from urllib.parse import urlsplit

import requests

from demo_app.transport import post_json


def check_connection() -> int:
    key = os.environ.get("THREATWATCH_INGESTION_KEY", "").strip()
    base_url = os.environ.get("THREATWATCH_URL", "http://127.0.0.1:5000").strip().rstrip("/")
    if not key:
        print("No ingestion key set in this terminal. Set THREATWATCH_INGESTION_KEY.")
        return 1
    if not re.fullmatch(r"[A-Za-z0-9_-]+", key):
        print(
            "Invalid ingestion key format: it contains whitespace, control characters, or symbols."
        )
        print("Copy only the key text, then set THREATWATCH_INGESTION_KEY again in this terminal.")
        print("Do not include quotes, the Bearer prefix, or the masked key prefix from Settings.")
        return 1
    try:
        parsed = urlsplit(base_url)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            raise ValueError
        print(f"Checking {parsed.scheme}://{parsed.hostname}:{parsed.port or 80}")
        response = post_json(
            base_url + "/api/v1/events",
            headers={"Authorization": f"Bearer {key}"},
            json={},  # Intentionally invalid: verifies auth/JSON without persisting data.
            timeout=5,
            allow_redirects=False,
        )
    except (ValueError, requests.RequestException):
        print(
            "Connection failed. Set THREATWATCH_URL=http://127.0.0.1:5000 and start the platform."
        )
        return 1
    try:
        payload = response.json()
    except ValueError:
        payload = None
    if (
        response.status_code == 422
        and isinstance(payload, dict)
        and isinstance(payload.get("error"), dict)
        and payload["error"].get("code") == "validation"
    ):
        print(
            "Connection OK: key authenticated and JSON reached event validation. No event stored."
        )
        return 0
    print(f"Connection check failed: HTTP {response.status_code}.")
    if response.status_code == 401:
        print(
            "Key rejected. Copy an active key from the application settings and restart the demo."
        )
    elif response.status_code == 400:
        csrf_error = (
            isinstance(payload, dict)
            and isinstance(payload.get("error"), dict)
            and ("CSRF" in str(payload["error"].get("message", "")))
        )
        if csrf_error:
            print(
                "The platform rejected API traffic for CSRF. Restart port 5000 with current code."
            )
        elif payload is None:
            # Recognize a fixed server diagnostic without exposing arbitrary response text.
            if "Invalid header" in response.text:
                print(
                    "HTTP server rejected an invalid header before the API could read the request."
                )
                print(
                    "Re-enter the ingestion key and retry. Do not include hidden paste characters."
                )
            else:
                print("Non-JSON rejection persists on a direct connection; check port 5000.")
        else:
            print("Platform rejected the request. Restart port 5000 with current code.")
    else:
        print("Check the platform terminal and confirm the URL points to port 5000.")
    return 1


if __name__ == "__main__":
    raise SystemExit(check_connection())
