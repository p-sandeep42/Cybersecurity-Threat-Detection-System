# ThreatWatch — local feature-complete demonstration

An application-owner dashboard and HTTP API for investigating suspicious authentication activity. The separate Papertrail demo bookstore reports login outcomes without waiting for the monitoring service.

## Implemented

- Owner login with password hashing, CSRF protection and owner-scoped application access.
- One-time-visible ingestion keys, immediate key rotation/revocation, application deletion.
- Strict event validation, canonical timestamps/IPs, idempotent delivery and conflicting-ID rejection.
- Three event-time rules: repeated failures, failures across accounts, success following failures.
- Evidence-linked incidents, late-event reconciliation, investigation notes and status history.
- Events/alerts filters, pagination, overview counts and backend response-duration percentiles.
- Separate demo login, bounded background queue, retries and explicit delivery-loss behavior.
- Explicit Alembic migration, pinned dependencies, automated tests and lint configuration.
- Explicitly opted-in browser summaries, pointer counts and interaction timing; never raw paths or typed text.
- Experimental BOT-001 automation indicator with evidence and documented false-positive/evasion limits.
- Five-second visible-tab refresh, pause controls, expired-session handling and preserved filter edits.
- Persisted delivery outcomes in the platform; queue/retry/drop diagnostics in the signed-in local demo.
- Scoped retention previews and purge commands; synthetic evaluation and measured HTTP benchmarks.
- Real Chromium consent, keyboard, touch, visibility and accessibility checks, plus desktop/mobile screenshots.

The planned local P0/P1 features are implemented. Hosted service, notifications, machine learning and automatic blocking are outside this release. “Feature-complete” does not imply production readiness or universal attack detection.

## Upgrade an existing installation

Stop both running servers with Ctrl+C. In the **platform terminal**, from `rebuild/`, run:

```powershell
../.venv/Scripts/python.exe -m pip install -r requirements.lock
../.venv/Scripts/python.exe -m flask --app platform_app init-db
../.venv/Scripts/waitress-serve.exe --listen=127.0.0.1:5000 --call platform_app:create_app
```

`init-db` now applies migration 0002 (delivery receipts and a session index) without deleting existing applications, keys, events or notes. Do not create another owner or rotate your key for this upgrade. Then restart the demo in its original terminal using the command below; that terminal retains its demo secret, password and key. Waitress does not reload changed code automatically.

## Local setup — Windows PowerShell

Run from the repository root. Python 3.13 is required. If `python` or `py` is unavailable, use the installed executable's full path.

```powershell
python -m venv .venv
.venv/Scripts/python.exe -m pip install -r rebuild/requirements.lock
Set-Location rebuild
$env:THREATWATCH_SECRET = (& ../.venv/Scripts/python.exe -c 'import secrets; print(secrets.token_hex(32))')
../.venv/Scripts/python.exe -m flask --app platform_app init-db
../.venv/Scripts/python.exe -m flask --app platform_app create-owner
../.venv/Scripts/waitress-serve.exe --listen=127.0.0.1:5000 --call platform_app:create_app
```

Open **http://127.0.0.1:5000**, sign in, create an application, and save its one-time ingestion key. The default database is `rebuild/instance/threatwatch.db`, excluded from Git. Keep a stable secret in your local shell configuration if you want sessions to survive restarts; do not commit it. The `.env.example` lists settings but is not loaded automatically.

On the current workstation, Python was found at `C:/Users/HP/AppData/Local/Programs/Python/Python313/python.exe`, and `.venv` is already installed. The commands above are portable setup instructions, not an assertion that Python is on PATH.

## Start the separate demo

Open another PowerShell terminal in `rebuild/`:

```powershell
$env:DEMO_SECRET = (& ../.venv/Scripts/python.exe -c 'import secrets; print(secrets.token_hex(32))')
$demoCredential = Read-Host 'Choose a synthetic demo password (at least 12 characters)' -AsSecureString
$env:DEMO_PASSWORD = [System.Net.NetworkCredential]::new('', $demoCredential).Password
$env:THREATWATCH_INGESTION_KEY = Read-Host 'Paste the application ingestion key'
../.venv/Scripts/waitress-serve.exe --listen=127.0.0.1:5001 --call demo_app:create_app
```

Open **http://127.0.0.1:5001** and log in as **reader** using your configured demo password. Five failures against the same username within five minutes should create AUTH-001; a subsequent successful login should create AUTH-003. Monitoring outages do not stop demo login. The demo intentionally allows repeated local login attempts for demonstration; it is not a production authentication service.

The demo holds its single synthetic credential as a password hash in memory; it does not yet need the separate account database proposed for later expansion. Its session secret and cookie name are independent from the platform's.

## Repeatable synthetic API scenario

In a third terminal at `rebuild/`, set the same ingestion key, then run:

```powershell
$env:THREATWATCH_INGESTION_KEY = Read-Host 'Paste the application ingestion key'
../.venv/Scripts/python.exe -m scripts.demo_scenario
```

This sends six synthetic records only to `127.0.0.1:5000`, with a new subject per run. It exercises ingestion and detection directly. The separate bookstore and end-to-end test exercise application instrumentation.

## Browser behavior and consent

On the demo login page, optional collection starts **off**. Choose **Enable measurements** to collect capped pointer-event counts and rounded timing durations. The choice lasts for the current tab session; **Disable measurements** removes listeners and clears the pending summary. Touch and keyboard-only access work. Hidden-page activity is not counted and interrupted intervals are excluded from timing metrics and BOT-001.

ThreatWatch displays summary availability, submit timing and first-interaction timing separately from backend response duration. Missing values remain unavailable, not zero. The demo backend independently determines authentication outcome, source IP and pseudonymous account identity. Invalid browser summaries are omitted without breaking login; the ingestion API rejects invalid submitted event fields.

BOT-001 flags at least 10 attempts in 60 seconds with at least 10 usable summaries, of which at least 80% report submission within 500 ms. Pointer counts do not affect the score. This is a Medium-priority investigation indicator, not proof that someone is a bot; no blocking occurs.

## Delivery and refresh

The overview shows accepted, duplicate and rejected HTTP submissions attributable to an active key. Counts use receipt time and honor the selected application/time range, but account/IP/outcome filters cannot apply to payload-free receipts. They start with migration 0002, not with older event history. Storage failures can also prevent receipt recording.

After signing into the bookstore as `reader`, open **Local operator: delivery status**. It shows queued, sent, retried, dropped, pending and worker state. This view requires a signed-in demo session and a direct loopback connection; it does not expose keys or event payloads. Queue counters reset when the demo restarts.

Overview, Events and Alerts refresh every five seconds while visible. Updates preserve filters and pause during result interaction; use the checkbox to stop them. Alert investigation forms do not auto-refresh. Session expiry stops polling with a sign-in message.

## Retention and purge

Retention is an explicit local-administrator operation, not a scheduled background job. The default cutoff is seven days ago. Preview one application's deletions:

```powershell
../.venv/Scripts/python.exe -m flask --app platform_app purge-data --application-id YOUR_APPLICATION_UUID
```

The UUID is visible in that application's dashboard URL. To execute a reviewed preview, repeat the command with `--apply`. Use `--before '2026-10-01T00:00:00Z'` for an explicit cutoff, or `--all-applications` instead of `--application-id` for all local applications. The CLI rejects ambiguous scope, timezone-free timestamps and future cutoffs.

Purge removes old events, any incident depending on those events, associated notes/evidence, audit references to deleted incidents, and old audit/delivery records. Recent evidence belonging to an expired incident remains as events but is not presented as an unsupported partial alert. Application deletion still removes the entire application. Purge is not run against your data by tests or benchmark scripts.

## API contract

See [architecture](../docs/plan/02-architecture.md) for the complete payload. Send one JSON event to `POST /api/v1/events` with `Authorization: Bearer <key>`. The API key sets application ownership; never put it in browser code. Reuse the original event ID on retries.

`201` means the event and its detection transaction committed; `200` is an identical duplicate; `409` is an ID/content conflict. Validation errors are `422`, unauthorized keys `401`, invalid JSON `400`, wrong content type `415`, oversized bodies `413`, rate limits `429`, and retryable transaction failures `503`.

## Verify changes

If demo logins do not appear in Events, stop the demo with Ctrl+C and run this
in that same terminal (its environment contains the configured key):

```powershell
../.venv/Scripts/python.exe -m scripts.check_connection
```

The check authenticates an intentionally incomplete event without storing it.
Local connections to localhost/loopback addresses bypass environment proxies
and netrc credentials, so a shell's proxy settings cannot redirect demo traffic.
Remote URLs retain the usual Requests environment configuration.
It reports connection/key errors without printing credentials. Restart the demo
afterwards with the Waitress command above. Restart an existing server after
code changes; Waitress does not reload code automatically.

From `rebuild/`:

```powershell
../.venv/Scripts/python.exe -m pytest -q
../.venv/Scripts/python.exe -m ruff check .
../.venv/Scripts/python.exe -m ruff format --check .
```

Run real-browser checks separately (development-only Node dependency; no frontend build is required):

```powershell
npm.cmd ci --ignore-scripts
$env:RUN_BROWSER_TESTS = '1'
../.venv/Scripts/python.exe -m pytest tests/test_browser.py -q
```

These checks use installed Chrome by default. Alternatively, run `../.venv/Scripts/python.exe -m playwright install chromium` and set `$env:BROWSER_CHANNEL = 'chromium'`. The tests use ephemeral servers and temporary databases, not ports 5000/5001 or your live accounts.

Reproduce the frozen evaluation and HTTP benchmark:

```powershell
../.venv/Scripts/python.exe -m scripts.evaluate_detection
../.venv/Scripts/python.exe -m scripts.benchmark
```

The benchmark runs 300 scheduled requests over approximately one minute with 10,000 seeded events, then measures 30 dashboard requests. It disables rate limiting only in the temporary lab because the production default of 120 requests/minute is below the benchmark's scheduled load. No real data is used.

Tests use temporary migrated databases and synthetic secrets. They cover thresholds, boundary timestamps, shuffled events, tenant isolation, CSRF, malformed payloads, retries, rollback, key lifecycle, alert reopening, late incident merges, and demo-to-platform integration. Passing fixture tests is not a real-world detection-accuracy measurement.

## Results and limitations

- [Synthetic held-out evaluation](reports/evaluation.md) includes false alarms and missed automation. It is a small authored fixture, not real-world accuracy evidence; do not market the rule scores as probabilities.
- [HTTP benchmark](reports/benchmark.md) records the workload, machine, observed results and limits. The original slower result is retained in `reports/benchmark-baseline.json`.
- [Browser verification](reports/browser-verification.md) records automated accessibility checks, behavioral checks and visual review. This is not an accessibility certification or exhaustive cross-browser coverage.
- The sender's queue is in memory; restart or exhausted retries can lose events. Failures are logged and exposed in the local operator's counters.
- Single-process, local SQLite and in-memory rate limiting only. There is no public registration, automatic blocking, notification delivery or hosted deployment.
- Benchmarks cover a benign shared-IP workload, not attack-heavy worst-case capacity. Browser summaries can be forged, shared IPs can produce false positives, and legitimate automation can look suspicious.
- Future public hosting requires the deployment controls described in the plan. This milestone binds both servers to loopback.

## Code map

`platform_app/schemas.py` owns input validation; `detection/` owns rule evaluation and reconciliation; `ingestion.py` owns the transactional API; `dashboard.py` owns owner-scoped views; `models.py` and `migrations/` own persistence; `demo_app/sender.py` owns best-effort delivery. The pure detector has no Flask or database dependencies.
