# Implementation plan and AI handoff

## Capacity and scope discipline

Plan for six days, four people, 1–2 hours each per day: 24–48 gross person-hours. AI can accelerate drafting but does not eliminate review, integration and debugging. The full specification is ambitious at the lower end. Deliver a tested P0 first; P1 is conditional. No development is authorized by these documents alone: this task creates the plan only.

The rebuild should later live in `rebuild/`, preserving the prototype. First inspect repository instructions and Git status; do not overwrite unrelated changes. Do not migrate old alert summaries into the new system because they lack event-level evidence.

## Ownership

| Owner | Main responsibility | Primary files |
|---|---|---|
| A: platform/integration lead | App factory, DB/migrations, ingestion, schema and auth boundaries | platform_app/{models,schemas,ingestion,auth,applications,cli}.py |
| B: detection/evaluation | Pure rules, time windows, episode reconciliation, fixtures and report | platform_app/detection/, tests/unit/, tests/scenarios/ |
| C: interface | Owner templates, lists/details, filters, summary rendering | platform_app/dashboard.py, templates/, static/ |
| D: demo/quality | Demo app, sender, optional telemetry, integration tests and CI | demo_app/, tests/integration/, workflow configuration |

Humans assign these roles at kickoff. Each person may use an AI coding assistant, but assistants do not edit another owner's files without coordination. A owns shared dependency/migration files. B and A agree the detector interface before parallel work; C works against agreed view-model fixtures until backend queries exist. D reviews the ingestion contract from a client perspective.

## Detector interface

Pure evaluation accepts validated events, fixed rule configuration/version and application scope; returns candidate episodes containing rule ID/version, entity key, ordered event IDs, start/end, reason, score and severity. It does not write a database or read the wall clock. Persistence reconciles episodes inside the ingestion transaction. Tests supply fixed timestamps. A and B freeze the concrete Python types before implementation.

## Six-day sequence

| Day | Parallel work | Exit gate |
|---|---|---|
| 1 | A scaffolds app/schema/migration/auth; B builds rule fixtures and pure rule functions; C builds static accessible page templates; D builds demo login and sender interface | Shared contract frozen; environments run; tests can execute |
| 2 | A completes authenticated ingestion/dedup; B implements episode generation; C connects app setup/event views; D connects demo sender | Demo login reaches platform; retry and duplicate tests pass |
| 3 | A/B integrate transactional reconciliation; C implements evidence/status/notes; D adds tenant/auth/outage tests | Three rules demonstrated end-to-end; P0 security tests pass |
| 4 | Fix P0 defects first; only then D adds opt-in telemetry, B adds BOT-001, C adds timing summaries, A adds purge | Feature gates pass or P1 visibly deferred |
| 5 | All run held-out scenarios and clean-setup trial; D runs CI; A benchmarks ingestion; C checks empty/error/mobile states | Evaluation report with actual results and known limitations |
| 6 | Buffer for fixes, review documentation, record short demo, prepare presentation and individual explanation | Release checklist signed off; no untested last-minute features |

If time is less than assumed: deliver CLI-provisioned one demo app per owner, login, ingestion, AUTH-001, evidence view and tests first. Label it a reduced milestone, not completion of the full PRD. Add AUTH-002/003 and lifecycle controls next. Do not remove tenant checks, validation, or honest limitations to preserve cosmetic features.

## Work packages and acceptance

| ID | Owner | Depends on | Required verification |
|---|---|---|---|
| T01 app structure/config/lock | A | none | Fresh environment starts; missing secret fails safely |
| T02 models/migrations | A | T01 | Empty DB migrates; constraints and cascades tested |
| T03 owner sessions/app keys | A | T02 | Password/session/CSRF and cross-owner tests |
| T04 strict event API | A | T03 | Status codes, size bounds, timestamp validation, duplicate conflict |
| T05 pure authentication rules | B | agreed schema | Threshold/window/distinct-count tests |
| T06 episodes/reconciliation | B+A | T02,T05 | Shuffled arrival equals ordered evaluation; reopen/merge tests |
| T07 event/rule transaction | A | T04,T06 | Injected detector failure rolls back event and retry succeeds |
| T08 dashboard/investigation | C | T03,T07 | Accurate counts, scoped filters, evidence, notes, persistent status |
| T09 demo/sender | D | T04 | Success/failure generated server-side; outage and retry counters |
| T10 browser summaries | D | T09, P0 gate | No pre-consent collection; opt-out and input modality checks |
| T11 BOT-001/timing | B+C | T10 | Exact trigger, spoofing limitation, percentile fixtures |
| T12 retention/deletion | A | T08 | No orphaned evidence; owner scope and confirmation |
| T13 evaluation/CI/release | D + all | T01–T09 minimum | Clean checkout, green tests, measured report and demo |

## AI task prompt template

Copy this into each implementation session and fill in one work package:

```text
Read docs/plan/README.md and the relevant PRD, architecture and feature sections.
Implement task [Txx] only. Your owned paths are [paths].
Inspect current code, repository instructions and Git status first.
Preserve unrelated edits and the existing prototype.
Use the exact API/schema/rule definitions; do not invent fields or thresholds.
Do not add dependencies or change shared files without coordinating with owner A.
Implement acceptance cases [list] and run the relevant tests.
Treat browser values as untrusted; scope every query by authenticated ownership.
Do not claim tests passed unless you ran them. Do not fabricate benchmark results.
If blocked by a contract conflict, report the conflict and a concrete proposed amendment.
Finish with files changed, behavior, commands actually run, results and remaining risks.
```

## Integration workflow

Use short task branches and small pull requests. Integrate at least daily. One teammate reviews each change, focusing on behavior and evidence rather than generated code volume. Contract changes require a documentation update before dependent code proceeds. Tests can run in parallel locally, but schema changes are owned by A. Keep secrets, DBs and generated private logs out of Git.

Review checklist: can the author explain the code; are inputs bounded; are ownership checks present; are timing/rule semantics exact; do retries preserve IDs; can browser data change trusted values; do tests cover a meaningful failure rather than merely repeat the implementation?

## Required verification matrix

- Unit: all rule thresholds/boundaries, canonicalization, percentiles and episode reconciliation.
- Integration: account isolation across every scoped route, CSRF, invalid/revoked keys, duplicate conflicts, transaction rollback, note escaping, deletion/retention if shipped.
- Sender: queue overflow, retry exhaustion, permanent 4xx, monitoring outage, process-restart loss documented.
- UI/manual: keyboard/touch, consent changes, no-data state, expired session, filters and readable evidence.
- Evaluation: held-out synthetic scenarios, counts/precision/recall per rule, false-positive examples, missing/spoofed telemetry.
- Performance: documented 10,000-event workload and targets from PRD; record observed numbers even if targets fail.

CI runs lint and deterministic unit/integration tests with temporary databases, fixed synthetic fixtures and test-only secrets. No live service or public website is required. Manual browser checks and benchmark results must be recorded separately from automated checks.

## Portfolio deliverables

1. README with truthful scope, setup, screenshots, limitations and architecture.
2. API reference and a working demo integration example.
3. Evaluation report listing fixture construction, rule versions, measured results and failure cases.
4. Three-to-five-minute demo: normal login, suspicious scenario, alert evidence, resolve, outage handling, optional telemetry.
5. Short decision record explaining rules over ML, alerting over blocking, and optional telemetry.
6. Each teammate can explain one rule, one security boundary, one failure mode and their contribution without AI assistance.

Release only the features that actually pass their acceptance checks. Public hosting, real-customer monitoring and production security claims are separate future work.
