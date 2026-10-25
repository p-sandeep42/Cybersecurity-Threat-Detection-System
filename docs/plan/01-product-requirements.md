# Product requirements

## Problem and outcome

Small application teams need a clear way to inspect suspicious login patterns without manually reading every log. ThreatWatch receives application events, identifies documented patterns, and connects alerts to evidence. It also displays optional interaction summaries and backend latency so an investigator can assess context.

The portfolio outcome is a reproducible demonstration of ingestion, security boundaries, deterministic detection, investigation, and honest evaluation. It is not a general intrusion prevention system or a guarantee of bot detection.

## Users and boundaries

- Owner: signs into ThreatWatch, creates applications, manages ingestion keys, views events and investigates alerts.
- Visitor: uses the separate demo application; may choose optional interaction collection. Does not need a ThreatWatch account.
- Evaluator: runs controlled scenarios and verifies expected results.

V1 supports multiple owner accounts with isolated application data, but one owner per application. Accounts are created through a local CLI; public registration, invitations, roles, password recovery, and email delivery are deferred. Two seeded owners are required for isolation tests.

## Main journeys

1. Owner logs in, registers an application, receives a one-time-visible key, and opens setup instructions.
2. Owner configures the application backend with the key and ingestion URL. A test event changes connection status from “No events received” to a last-received timestamp.
3. Visitor attempts login. The backend determines the outcome and queues a security event independently of the login response.
4. ThreatWatch authenticates the sender, validates the event, persists it, and evaluates relevant rules.
5. Owner sees an alert, opens the evidence timeline, adds a note, and marks it Investigating or Resolved.
6. Owner compares suspicious patterns with application latency and optional client summaries. Missing client data remains unknown, never proof of automation.

## Scope and priorities

| Priority | Deliverable |
|---|---|
| P0: release gate | Owner login; tenant isolation; app/key management; validated event API; deduplication; three authentication rules; evidence view; status/notes; demo integration; evaluation tests |
| P1: planned if P0 passes | Optional interaction summaries; experimental automation indicator; latency summaries; documented retention/purge commands |
| P2: after deadline | Hosted service; durable sender queue; CSV import; collectors; notifications; role management; configurable rule UI; external reputation; ML experiments |

P1 is specified fully to avoid guesswork but must not delay a working P0. If omitted, the demo and README must explicitly say so. Backend duration capture is cheap enough to include in P0; aggregate charts may wait until P1.

## Success and acceptance

- A clean checkout can be configured and run by following documented local steps without editing source code.
- A valid demo event appears in the event view; the three labeled suspicious scenarios generate the expected rule alerts with evidence.
- All curated benign scenarios avoid authentication alerts at the chosen thresholds; this is a fixture requirement, not a real-world false-positive claim.
- Duplicate delivery neither duplicates events nor increases rule counts.
- Two owners cannot read or change one another’s applications, keys, events, notes, or alerts, including guessed IDs.
- Demo login continues during a monitoring outage; lost/dropped events are visible in sender counters.
- Opting out produces no interaction summaries and does not affect login or rule evaluation.
- Timing charts distinguish backend execution time from visitor interaction time. Neither is labeled network latency.
- Core tests, isolation tests, and a reproducible evaluation report pass before release.

## Quality targets to measure

On a documented developer laptop with 10,000 seeded events: ingestion p95 under 500 ms at five single-event requests/second for 60 seconds; dashboard query p95 under one second over 30 measurements; accepted alerts visible within a five-second polling interval plus request time. Record hardware, versions, workload, failures, and achieved values. Missed targets are reported and investigated, never replaced by invented results.

## Privacy and security posture

Use synthetic identities and documentation-range IP addresses in published examples. Production IPs and user identifiers would still be sensitive even without names. Collect the minimum fields listed in the contract; exclude passwords, tokens, query strings, free-form request bodies, mouse coordinates, and typed contents.

Proposed default retention is seven days for events and associated client summaries; purge dependent evidence, affected alerts, and notes together so the system does not display unsupported alerts. Keep operational logs and audit entries seven days without event payloads. Retention runs via an explicit CLI command in the local MVP; it is not automatic until scheduling is implemented. Application deletion immediately removes its data and revokes keys, after a clear confirmation.

Browser consent applies to optional client summaries. Essential backend security-event processing has a separate notice; opt-out must not be represented as disabling all server logging. This design is a demo privacy policy, not a claim of legal compliance.

## Exclusions and risks

No automatic blocking, malware scanning, vulnerability scanning, device fingerprinting, keystroke biometrics, cross-site tracking, or universal bot classifier. Shared IPs, legitimate automation, autofill, accessibility tools, missing telemetry, forged browser signals, and stolen ingestion keys limit conclusions. Prototype thresholds need tuning against representative authorized data before operational use.
