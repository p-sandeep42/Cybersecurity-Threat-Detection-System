"""Score frozen holdout incidents once per rule/entity with overlapping evidence."""

import hashlib
import json
from pathlib import Path

from platform_app.detection import RULES, evaluate


def run_evaluation():
    root = Path(__file__).parents[1]
    fixture = root / "evaluation" / "holdout-v1.json"
    content = fixture.read_bytes()
    scenarios = json.loads(content)["scenarios"]
    counts = {rule: {"TP": 0, "FP": 0, "FN": 0} for rule in RULES}
    details = []
    for case in scenarios:
        actual = evaluate(case["events"])
        unmatched = set(range(len(actual)))
        for expected in case["expected_incidents"]:
            match = next(
                (
                    index
                    for index in sorted(unmatched)
                    if actual[index].rule_id == expected["rule_id"]
                    and actual[index].entity_key == expected["entity_key"]
                    and actual[index].evidence.intersection(expected["event_ids"])
                ),
                None,
            )
            if match is None:
                counts[expected["rule_id"]]["FN"] += 1
            else:
                counts[expected["rule_id"]]["TP"] += 1
                unmatched.remove(match)
        for index in unmatched:
            counts[actual[index].rule_id]["FP"] += 1
        details.append(
            {
                "scenario": case["name"],
                "expected": [e["rule_id"] for e in case["expected_incidents"]],
                "observed": [a.rule_id for a in actual],
                "note": case["note"],
            }
        )
    for values in counts.values():
        tp, fp, fn = values["TP"], values["FP"], values["FN"]
        values["precision"] = round(tp / (tp + fp), 4) if tp + fp else None
        values["recall"] = round(tp / (tp + fn), 4) if tp + fn else None
    report = {
        "fixture_sha256": hashlib.sha256(content).hexdigest(),
        "scenarios": len(scenarios),
        "events": sum(len(case["events"]) for case in scenarios),
        "rules": counts,
        "details": details,
    }
    reports = root / "reports"
    reports.mkdir(exist_ok=True)
    (reports / "evaluation.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    lines = [
        "# Synthetic held-out evaluation",
        "",
        f"Frozen fixture SHA-256: `{report['fixture_sha256']}`",
        "",
        f"{report['scenarios']} scenarios, {report['events']} events. Rule versions: v1.",
        "",
        "This small, hand-authored synthetic holdout was not used to tune the thresholds. "
        "It is not an independent real-world dataset. "
        "Scores below describe only these stipulated scenarios.",
        "",
        "Matching is one-to-one by rule/entity and overlapping labeled evidence; "
        "extra incidents count as false positives.",
        "",
        "| Rule | TP | FP | FN | Precision | Recall |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for rule, result in counts.items():
        lines.append(
            f"| {rule} | {result['TP']} | {result['FP']} | {result['FN']} | "
            f"{result['precision']} | {result['recall']} |"
        )
    lines.extend(
        ["", "## Scenario results", "", "| Scenario | Expected | Observed |", "|---|---|---|"]
    )
    for detail in details:
        lines.append(
            f"| {detail['scenario']} | {', '.join(detail['expected']) or 'None'} | "
            f"{', '.join(detail['observed']) or 'None'} |"
        )
    lines.extend(
        [
            "",
            "## Limits",
            "",
            "Shared IPs and authorized fast automation produce false alarms. "
            "Missing or forged timing can evade BOT-001. Mouse counts do not establish identity; "
            "missing telemetry does not establish safety. Thresholds were not adjusted after "
            "these results. N/A (null in JSON) denotes an undefined denominator.",
        ]
    )
    (reports / "evaluation.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps(counts, indent=2))


if __name__ == "__main__":
    run_evaluation()
