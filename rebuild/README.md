# ThreatWatch — first implementation milestone

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

This is an initial working milestone, not completion of every item in the planning package.

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

Tests use temporary migrated databases and synthetic secrets. They cover thresholds, boundary timestamps, shuffled events, tenant isolation, CSRF, malformed payloads, retries, rollback, key lifecycle, alert reopening, late incident merges, and demo-to-platform integration. Passing fixture tests is not a real-world detection-accuracy measurement.

## Next milestones and current limitations

- Browser summaries, opt-in collection, BOT-001 and interaction-duration metrics are not implemented. The API can validate/store optional summaries, but the demo sends null. No mouse tracking runs.
- Dashboard refresh is manual. Persisted rejection/duplicate counters, sender-counter UI, retention CLI and audit-log purge remain to be added.
- The sender's queue is in memory; restart or exhausted retries can lose events. Failures are logged; counters are available through `EventSender.snapshot()` for tests/operator instrumentation.
- Single-process, local SQLite and in-memory rate limiting only. There is no public registration, automatic blocking, notification delivery or hosted deployment.
- Held-out evaluation, performance benchmarks and browser visual/accessibility checks remain outstanding. No accuracy or throughput figures are claimed.
- Future public hosting requires the deployment controls described in the plan. This milestone binds both servers to loopback.

## Code map

`platform_app/schemas.py` owns input validation; `detection/` owns rule evaluation and reconciliation; `ingestion.py` owns the transactional API; `dashboard.py` owns owner-scoped views; `models.py` and `migrations/` own persistence; `demo_app/sender.py` owns best-effort delivery. The pure detector has no Flask or database dependencies.
