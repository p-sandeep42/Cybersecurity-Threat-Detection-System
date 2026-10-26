# Synthetic held-out evaluation

Frozen fixture SHA-256: `8e08702b70cd412a86b0071a6e76e5f9479601cab3fb0a995ba8d49cf7e95dad`

15 scenarios, 130 events. Rule versions: v1.

This small, hand-authored synthetic holdout was not used to tune the implemented thresholds. It is not an independent real-world dataset. Scores below describe only these stipulated scenarios.

Matching is one-to-one by rule/entity and overlapping labeled evidence; extra incidents count as false positives.

| Rule | TP | FP | FN | Precision | Recall |
|---|---:|---:|---:|---:|---:|
| AUTH-001 | 3 | 0 | 0 | 1.0 | 1.0 |
| AUTH-002 | 1 | 1 | 0 | 0.5 | 1.0 |
| AUTH-003 | 1 | 0 | 0 | 1.0 | 1.0 |
| BOT-001 | 1 | 1 | 2 | 0.5 | 0.3333 |

## Scenario results

| Scenario | Expected | Observed |
|---|---|---|
| normal-successes | None | None |
| ordinary-corrections | None | None |
| brute-force | AUTH-001 | AUTH-001 |
| password-spray | AUTH-002 | AUTH-002 |
| success-after-failures | AUTH-001, AUTH-003 | AUTH-001, AUTH-003 |
| shuffled-brute-force | AUTH-001 | AUTH-001 |
| rapid-automation | BOT-001 | BOT-001 |
| touch-visitor | None | None |
| keyboard-visitor | None | None |
| single-autofill | None | None |
| hidden-tab | None | None |
| shared-office-benign-failures | None | AUTH-002 |
| approved-fast-automation | None | BOT-001 |
| bot-without-telemetry | BOT-001 | None |
| bot-spoofing-slow-timing | BOT-001 | None |

## Limits

Shared IPs and authorized fast automation produce false alarms. Missing or forged timing can evade BOT-001. Mouse counts do not establish identity, and missing telemetry does not establish safety. Thresholds were not adjusted after these results. N/A (null in JSON) denotes an undefined denominator.
