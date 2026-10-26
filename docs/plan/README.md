# ThreatWatch planning package

Status: planning baseline. The local P0/P1 implementation now lives in [rebuild](../../rebuild/README.md); measured results and remaining production limitations are recorded there.
Prepared: 25 October 2026. Working name: ThreatWatch.

## Read in this order

1. [Product requirements](01-product-requirements.md)
2. [Architecture and integration contract](02-architecture.md)
3. [Technology decisions](03-tech-stack.md)
4. [Detailed features and detection specification](04-features.md)
5. [Implementation and AI handoff plan](05-implementation.md)

## Decisions made from the discussion

- Positioning: security engineering with demonstrable full-stack skills.
- Audience: application owners investigating suspicious authentication activity.
- Four students; plan assumes 1–2 hours per student per day, six working days: 24–48 person-hours before coordination overhead. This assumption is not a confirmed availability commitment.
- Local-first demonstration with one integrated demo application and a documented HTTP API. Public hosting is a later milestone.
- Alert and investigate only. Do not block users, inject challenges, or call a suspicious user an attacker.
- Browser summaries are optional, disabled by default, and enabled only after an explicit notice and opt-in. No raw mouse paths, typed text, fingerprints, or recordings.
- Measure interaction timing and backend response duration separately.
- Rules and synthetic evaluation first; no machine learning requirement.
- Rebuild in a new directory later; preserve the current prototype and Git history.

## Contract authority

PRD governs scope; architecture governs API/schema; features govern rule semantics; implementation governs order and ownership. If these conflict, stop the affected task and record a decision rather than silently inventing behavior. Future changes must update all affected documents in the same pull request.

These documents resolve implementation choices with explicit defaults. Actual capacity, accuracy, and hosting suitability require measurement; no document can establish those in advance.

## Remaining external uncertainties

| Uncertainty | Default until clarified | Consequence |
|---|---|---|
| Exact college submission date | Six-day schedule starting when implementation is authorized | Move to reduced milestone if time is shorter |
| Meaning of 1–2 hours | Per person per day | If total team time is smaller, use reduced milestone |
| Individual skills and equipment | All can run Python locally; assign owners at kickoff | Swap ownership, not API contracts |
| Hosting provider/domain | None selected | No deployment cost or public availability promise |
| Real customer use/jurisdiction | Synthetic demo data only | Real-data privacy and operational requirements need a separate review |

No further answer is required to use this local demonstration plan. None of the proposed performance targets or test results are claims of completed work.
