"""Best-effort background delivery. Never block a visitor on monitoring availability."""

import logging
import random
import re
import threading
from collections import Counter
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from queue import Empty, Full, Queue

import requests

from demo_app.transport import post_json

logger = logging.getLogger(__name__)


class EventSender:
    def __init__(self, base_url: str, key: str, capacity: int = 100):
        self.url = base_url.rstrip("/") + "/api/v1/events"
        self.key = key.strip()
        if not re.fullmatch(r"[A-Za-z0-9_-]+", self.key):
            raise ValueError(
                "Invalid ingestion key format. Copy only the key text into "
                "THREATWATCH_INGESTION_KEY; remove spaces, quotes and hidden paste characters."
            )
        self.queue = Queue(maxsize=capacity)
        self.counters = Counter()
        self.lock = threading.Lock()
        self.stopped = threading.Event()
        self.worker = None

    def start(self):
        self.worker = threading.Thread(target=self._run, name="event-sender", daemon=True)
        self.worker.start()

    def stop(self):
        self.stopped.set()
        if self.worker:
            self.worker.join(timeout=3)

    def _count(self, name):
        with self.lock:
            self.counters[name] += 1

    def snapshot(self):
        with self.lock:
            return {name: self.counters[name] for name in ("queued", "sent", "retried", "dropped")}

    def enqueue(self, event: dict) -> bool:
        try:
            self.queue.put_nowait(event)
        except Full:
            self._count("dropped")
            logger.warning("Monitoring queue full; newest event dropped")
            return False
        self._count("queued")
        return True

    @staticmethod
    def retry_delay(response, attempt):
        delay = 2**attempt + random.uniform(0, 0.25)
        if response is None:
            return delay
        header = response.headers.get("Retry-After", "")
        try:
            requested = float(header)
        except ValueError:
            try:
                requested = (parsedate_to_datetime(header) - datetime.now(UTC)).total_seconds()
            except (ValueError, TypeError, OverflowError):
                requested = 0
        return max(delay, requested)

    def deliver(self, event: dict) -> bool:
        failure_reason = "No response from the monitoring platform"
        for attempt in range(4):
            response = None
            try:
                response = post_json(
                    self.url,
                    json=event,
                    headers={"Authorization": f"Bearer {self.key}"},
                    timeout=2,
                    allow_redirects=False,
                )
                if response.status_code in {200, 201}:
                    self._count("sent")
                    return True
                failure_reason = self.describe_rejection(response.status_code)
                if response.status_code != 429 and response.status_code < 500:
                    break
            except requests.Timeout:
                failure_reason = (
                    "Connection timed out; check that ThreatWatch is responding on port 5000"
                )
            except requests.ConnectionError:
                failure_reason = (
                    "Cannot connect; start ThreatWatch on port 5000 and check THREATWATCH_URL"
                )
            except requests.RequestException:
                failure_reason = (
                    "Request failed; check THREATWATCH_URL and the ingestion key format"
                )
            if attempt == 3 or self.stopped.is_set():
                break
            self._count("retried")
            if self.stopped.wait(self.retry_delay(response, attempt)):
                break
        self._count("dropped")
        logger.warning("Monitoring delivery failed: %s. Event dropped.", failure_reason)
        return False

    @staticmethod
    def describe_rejection(status: int) -> str:
        """Use fixed messages: response bodies may contain sensitive or untrusted data."""
        explanations = {
            400: "Request rejected; run python -m scripts.check_connection in the demo terminal",
            401: "Ingestion key rejected; copy an active application key and restart the demo",
            404: "Ingestion endpoint not found; check THREATWATCH_URL points to the platform",
            409: "Event ID conflicts with an existing event",
            422: "Event validation failed; check the machine clock and event format",
            429: "Ingestion rate limit reached; wait before trying again",
            503: "Platform transaction failed; inspect the ThreatWatch terminal",
        }
        return f"HTTP {status}: {explanations.get(status, 'Unexpected platform response')}"

    def _run(self):
        while not self.stopped.is_set():
            try:
                event = self.queue.get(timeout=0.25)
            except Empty:
                continue
            try:
                self.deliver(event)
            finally:
                self.queue.task_done()
