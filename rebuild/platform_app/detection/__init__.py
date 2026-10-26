"""Pure event-time rules. Scores are triage priorities, never probabilities."""

from collections import defaultdict, deque
from dataclasses import dataclass
from datetime import datetime, timedelta


@dataclass(frozen=True)
class Episode:
    rule_id: str
    entity_key: str
    evidence: frozenset[str]
    start: str
    end: str
    score: int
    severity: str
    reason: str
    thresholds: dict


RULES = {
    "AUTH-001": (60, "High", "Repeated login failures", {"failures": 5, "window_seconds": 300}),
    "AUTH-002": (
        70,
        "High",
        "Failures across multiple accounts",
        {"distinct_subjects": 10, "window_seconds": 300},
    ),
    "AUTH-003": (
        85,
        "Critical",
        "Successful login after failures",
        {"failures": 5, "window_seconds": 600},
    ),
}


def evaluate(events: list[dict]) -> list[Episode]:
    """Evaluate one application's events, independent of arrival order or wall clock.

    Candidate windows sharing evidence form one incident. Disjoint windows stay
    separate even when their counts, scores and subjects are identical.
    """
    ordered = sorted(events, key=lambda item: (item["occurred_at"], item["event_id"]))
    by_subject = defaultdict(list)
    by_ip = defaultdict(list)
    for item in ordered:
        by_subject[item["subject_id"]].append(item)
        by_ip[item["source_ip"]].append(item)

    candidates = defaultdict(list)
    for subject, items in by_subject.items():
        failures = deque()
        for item in items:
            current = datetime.fromisoformat(item["occurred_at"])
            while failures and current - failures[0][0] > timedelta(minutes=10):
                failures.popleft()
            if item["outcome"] == "failure":
                failures.append((current, item))
                window = [
                    event for time, event in failures if current - time <= timedelta(minutes=5)
                ]
                if len(window) >= 5:
                    candidates[("AUTH-001", subject)].append(window)
            else:
                preceding = [event for time, event in failures if time < current]
                if len(preceding) >= 5:
                    candidates[("AUTH-003", subject)].append([*preceding, item])

    for address, items in by_ip.items():
        failures = deque()
        for item in items:
            if item["outcome"] != "failure":
                continue
            current = datetime.fromisoformat(item["occurred_at"])
            while failures and current - failures[0][0] > timedelta(minutes=5):
                failures.popleft()
            failures.append((current, item))
            window = [event for _, event in failures]
            if len({event["subject_id"] for event in window}) >= 10:
                candidates[("AUTH-002", address)].append(window)

    lookup = {item["event_id"]: item for item in ordered}
    episodes = []
    for (rule_id, entity), windows in candidates.items():
        merged: list[set[str]] = []
        for window in windows:
            evidence = {item["event_id"] for item in window}
            overlapping = [group for group in merged if group & evidence]
            for group in overlapping:
                evidence.update(group)
                merged.remove(group)
            merged.append(evidence)
        score, severity, reason, thresholds = RULES[rule_id]
        for evidence in merged:
            times = [lookup[event_id]["occurred_at"] for event_id in evidence]
            episodes.append(
                Episode(
                    rule_id,
                    entity,
                    frozenset(evidence),
                    min(times),
                    max(times),
                    score,
                    severity,
                    reason,
                    thresholds.copy(),
                )
            )
    return sorted(
        episodes, key=lambda episode: (episode.start, episode.rule_id, episode.entity_key)
    )
