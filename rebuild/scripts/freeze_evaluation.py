"""Build the versioned synthetic holdout before running evaluation.

Labels describe the scenario's stipulated ground truth, not rule output.
Do not alter thresholds or labels to improve the resulting report.
"""

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

BASE = datetime(2026, 1, 15, 12, tzinfo=UTC)


def scenario(
    name,
    count,
    *,
    outcome="success",
    spacing=2,
    interaction=None,
    subjects=False,
    offsets=None,
    expected=(),
    note="",
    shuffled=False,
):
    events = []
    for index in range(count):
        events.append(
            {
                "schema_version": 1,
                "event_id": str(uuid5(NAMESPACE_URL, f"{name}/{index}")),
                "occurred_at": (
                    BASE + timedelta(seconds=offsets[index] if offsets else index * spacing)
                ).isoformat(timespec="microseconds"),
                "event_type": "login",
                "outcome": outcome[index] if isinstance(outcome, list) else outcome,
                "subject_id": f"user-{index}" if subjects else "user-a",
                "source_ip": "203.0.113.10",
                "session_id": str(uuid5(NAMESPACE_URL, name)),
                "route": "/login",
                "response_duration_ms": 73.0,
                "interaction": interaction,
            }
        )
    labels = []
    for rule in expected:
        entity = (
            events[0]["session_id"]
            if rule == "BOT-001"
            else (events[0]["source_ip"] if rule == "AUTH-002" else "user-a")
        )
        evidence = [
            event["event_id"]
            for event in events
            if rule != "AUTH-001" or event["outcome"] == "failure"
        ]
        labels.append({"rule_id": rule, "entity_key": entity, "event_ids": evidence})
    if shuffled:
        import random

        random.Random(2407).shuffle(events)
    return {"name": name, "note": note, "events": events, "expected_incidents": labels}


def main():
    fast = {
        "version": 1,
        "consent": True,
        "pointer_type": "unknown",
        "pointer_move_count": 0,
        "pointer_down_count": 0,
        "first_interaction_ms": None,
        "submit_elapsed_ms": 200,
        "visibility_interrupted": False,
    }
    cases = [
        scenario("normal-successes", 15, spacing=91),
        scenario("ordinary-corrections", 4, outcome=["failure", "success", "failure", "success"]),
        scenario("brute-force", 7, outcome="failure", spacing=17, expected=("AUTH-001",)),
        scenario("password-spray", 12, outcome="failure", subjects=True, expected=("AUTH-002",)),
        scenario(
            "success-after-failures",
            6,
            outcome=["failure"] * 5 + ["success"],
            expected=("AUTH-001", "AUTH-003"),
        ),
        scenario(
            "shuffled-brute-force", 6, outcome="failure", expected=("AUTH-001",), shuffled=True
        ),
        scenario("rapid-automation", 12, interaction=fast, expected=("BOT-001",)),
        scenario(
            "touch-visitor",
            3,
            interaction={**fast, "pointer_type": "touch", "submit_elapsed_ms": 2600},
        ),
        scenario("keyboard-visitor", 4, interaction={**fast, "submit_elapsed_ms": 3100}),
        scenario("single-autofill", 1, interaction=fast),
        scenario("hidden-tab", 12, interaction={**fast, "visibility_interrupted": True}),
        scenario(
            "shared-office-benign-failures",
            12,
            outcome="failure",
            subjects=True,
            note=(
                "Distinct legitimate users mistype passwords behind one shared IP; "
                "expected false alarm."
            ),
        ),
        scenario(
            "approved-fast-automation",
            12,
            interaction=fast,
            note=(
                "Authorized test automation; behavior matches heuristic "
                "despite benign ground truth."
            ),
        ),
        scenario(
            "bot-without-telemetry",
            12,
            expected=("BOT-001",),
            note="Stipulated automation omits browser data; expected miss.",
        ),
        scenario(
            "bot-spoofing-slow-timing",
            12,
            interaction={**fast, "submit_elapsed_ms": 5000},
            expected=("BOT-001",),
            note="Stipulated automation forges slow durations; expected miss.",
        ),
    ]
    target = Path(__file__).parents[1] / "evaluation" / "holdout-v1.json"
    if target.exists():
        raise SystemExit(
            "Frozen holdout already exists; use a new version instead of overwriting labels."
        )
    target.parent.mkdir(exist_ok=True)
    target.write_text(
        json.dumps({"version": 1, "seed": 2407, "scenarios": cases}, indent=2), encoding="utf-8"
    )
    print(f"Frozen {len(cases)} synthetic scenarios in {target.name}")


if __name__ == "__main__":
    main()
