# Detailed feature specification

## F01 — Owner access and application setup (P0)

Create owners through a local administrative CLI with prompted passwords, never command-line passwords. Login uses generic failure messages. After login, display owned applications, last received event, active key prefix, and setup status. Create an application with a name; show a new ingestion key once and warn that navigating away hides it. Rotation and deletion require explicit confirmation. Revoke immediately. Audit key operations without recording keys.

Acceptance: unauthenticated dashboard redirects to login; valid login works; wrong credentials fail; missing CSRF fails; owner B cannot access any resource belonging to owner A; revoked keys receive 401; ingestion keys cannot access dashboard pages.

## F02 — Integration and event validation (P0)

Implement the architecture contract exactly. The setup page shows a sanitized request example and integration steps: configure backend environment, derive outcome on the server, enqueue events, send a test login, verify last-received time. Show counters for total stored events, rejected submissions where safely attributable, and duplicate deliveries. Never include authorization headers in logs.

Reject an entire event on invalid interaction data; the sender logs the safe error and does not silently strip fields/retry as a different payload. Owner connection state distinguishes “No events yet” from “Last event received at …”; lack of recent logins does not prove an outage.

Acceptance: valid success/failure events persist; same ID/content is idempotent; same ID/different content gets 409; malformed dates, nonfinite durations, oversized bodies, unsupported types and extra fields fail; an outage does not interrupt demo login.

## F03 — Authentication detection (P0)

All thresholds below are initial design parameters, not industry standards. Store rule ID/version and matched thresholds with each alert. Windows include both endpoints. Use canonical IPs and exact opaque subject IDs. Sorting tie-breaker is event UUID. Account-specific events from different IPs can contribute to the same account rule.

| Rule/version | Exact trigger and grouping | Score/severity | Evidence |
|---|---|---|---|
| AUTH-001/v1 | >=5 failed logins for one subject in any trailing 5-minute window | 60 / High | All failures in each qualifying window |
| AUTH-002/v1 | One IP fails against >=10 distinct subjects in a trailing 5-minute window | 70 / High | All failures from that IP in qualifying windows, including repeats |
| AUTH-003/v1 | A successful login for a subject has >=5 failures in the preceding 10 minutes; failures must precede success strictly | 85 / Critical | Success and preceding failures; source IP need not match |

Score labels: 0–29 Low, 30–59 Medium, 60–79 High, 80–100 Critical. Scores represent fixed triage priority, never probability. Rules produce separate alerts; do not sum overlapping scores. A subject or IP's displayed priority is the maximum score of its Open/Investigating alerts in the selected period, not an accumulated “risk percentage.”

AUTH-001 and AUTH-003 group by subject; AUTH-002 groups by IP. Episode formation and late-data reconciliation follow architecture. Alert title says “Repeated login failures,” “Failures across multiple accounts,” or “Successful login after failures.” The latter does not claim the account was compromised.

Required tests: one below/exactly at threshold; event exactly at window boundary and one millisecond outside; distinct-account counting; successes do not count as failures; duplicate delivery; equal timestamps; out-of-order arrivals; separate episodes with identical counts; tenants using same subject/IP; resolving and reopening with new evidence.

## F04 — Optional browser interaction summaries (P1)

Demo login page displays: “Optional interaction measurements help demonstrate suspicious-activity analysis. If enabled, we send counts of pointer activity and time to submit, not your typed text or mouse path. Login works without this.” Provide Enable and Continue without buttons. Default is disabled; choice lasts only for the current browser session. Provide a visible switch to disable and clear in-memory measurements. No pre-consent listeners or summaries. Backend login event reporting remains active and is separately described.

When enabled, initialize a monotonic timer and count pointermove events at most once per 100 ms and pointerdown events. Capture the first pointerdown or keydown time, but never the key, target field, input value or coordinates. Count no events while the document is hidden. A visibility change sets `visibility_interrupted=true`; timing stays elapsed wall duration and is excluded from automation evaluation. Each submission resets the counters and clock after completion; a full navigation naturally starts a new interval.

Exact interaction object (all fields required if non-null):

```json
{
  "version": 1,
  "consent": true,
  "pointer_type": "mouse",
  "pointer_move_count": 12,
  "pointer_down_count": 1,
  "first_interaction_ms": 420,
  "submit_elapsed_ms": 2800,
  "visibility_interrupted": false
}
```

`pointer_type` is `mouse`, `touch`, `pen`, `mixed`, or `unknown` based on observed pointer events; never infer disability. Counts are integers 0–100000. Durations are integers rounded to nearest 10 ms, range 0–1800000; first interaction may be null, otherwise it cannot exceed submit duration. Consent must be true. If interval exceeds 30 minutes or there is no consent, send null. Label data source “Browser-reported, unverified.” Null is “Not available,” never zero.

Acceptance: no collection before enable; disable stops listeners/clears data; keyboard-only and touch login work; no coordinates or key values in payload; hidden-page intervals are labeled; browser data cannot overwrite server outcome/identity/duration. Tampering can change the summary, which is explicitly not an integrity-protected signal.

## F05 — Experimental automation indicator (P1)

BOT-001/v1 groups login events by session ID. Trigger Medium/40 only when a trailing 60-second window has >=10 attempts, at least 10 valid opted-in non-interrupted summaries, and at least 80% of those summaries report submission within 500 ms. All attempts in the qualifying window are evidence. Use the same episode algorithm as authentication rules.

Pointer counts are visible context but do not contribute to scoring in V1. This is an intentional accessibility safeguard and avoids pretending that a short mouse sample establishes identity. Label the alert “Rapid repeated submissions — possible automation,” with observed counts, threshold, and a note that legitimate automation/autofill can match. No browser summary means this rule cannot evaluate, not that the session is safe. Server authentication rules still operate normally.

Acceptance: fast single submission, absent pointer data, touch, keyboard-only access and missing telemetry alone never trigger BOT-001. A controlled repeated-submission scenario does trigger. Forged slow timing can evade it; record that limitation in the evaluation.

## F06 — Response and interaction timing (P0 capture, P1 summaries)

Backend `response_duration_ms` starts at request entry and ends after login handling, before enqueue/network delivery and socket transmission. Use a monotonic server timer. It measures backend handling time, not browser round-trip or page rendering. On the dashboard show sample count, p50 and p95 by route and selected period; compute percentiles with nearest-rank (`ceil(p*n)-1`, sorted ascending), show N/A for no samples. Fewer than 20 samples display “Small sample.” Failed and successful login samples can be filtered separately.

Interaction panel shows median/p95 submit duration and first-interaction duration for available, non-interrupted summaries, excluding null first-interaction values from that metric's denominator. Show opted-in sample count and missing count; do not compare these directly to backend duration as if they measure the same thing. Slow backend duration never increases security scores.

Acceptance: known duration fixture has exact expected percentiles; no-data state renders; null is not treated as zero; elevated latency creates no threat alert.

## F07 — Dashboard and investigation (P0)

Overview cards: stored login events, failures, distinct attempted subjects, Open/Investigating alerts, Critical alerts, and flagged subjects/IPs. All cards honor selected application and time period. Count alerts whose episode_end is in the period; count events by occurred_at. Flagged entities come from active alerts in that period; an IP is not labeled a person. Display UTC explicitly. Last received event uses received_at and is labeled separately.

Events table: event time, received time, subject, IP, outcome, route, backend duration and client-data availability. Alert table: title, entity, rule, score/severity, first/last evidence times, status. Details: exact reason, thresholds, chronological evidence, optional interaction context, notes and audit history. Empty, loading, expired-session and error states are required. Support keyboard navigation and textual severity labels rather than color alone.

Status values: Open, Investigating, Resolved. Owner can move between any states; every change is audited. Notes are append-only plain text. Rule-driven reopening follows architecture. Do not provide a “block” button or fake notification controls.

Acceptance: filters/pagination work together; browser text is escaped; status and notes survive restart; duplicate ingestion preserves status; changed evidence reopens a resolved alert; two owners remain isolated.

## F08 — Demo, evaluation and data lifecycle (P0 except purge P1)

Provide a small application with synthetic accounts, login/logout, optional interaction controls, and integration status for the local operator. Use real password verification for the demo; never intentionally introduce injection vulnerabilities. Demonstrate five normal spaced logins, benign corrections below threshold, brute force, password spray, success after failures, and optional rapid submissions.

Scenario runner targets only the local demo by default, at bounded rates and with synthetic accounts. A separate fixture evaluator feeds timestamped events into the detector without waiting real minutes. Do not expose an unauthenticated endpoint that generates arbitrary traffic or accepts arbitrary target URLs.

Report per-rule scenario-level TP/FP/FN, precision and recall; denominator zero is N/A. Map expected incidents to rule/entity/evidence so one incident cannot count multiple times. Publish fixture size, conditions, rule versions and limitations. Separate deterministic correctness tests from held-out scenario evaluation; no tuning on the held-out set. Include at least shared-IP benign activity, autofill, keyboard/touch, shuffled arrival, missing telemetry, and deliberately spoofed browser summaries.

Purge command accepts an explicit UTC cutoff, defaults to seven days before now, and reports deleted counts. If an alert references any deleted evidence, delete that alert and dependent notes/evidence links; this conservative policy avoids misleading partial evidence. Delete audit entries older than seven days separately. Document that the command must be run manually in local V1. Application deletion cascades all owned application data and keys.
