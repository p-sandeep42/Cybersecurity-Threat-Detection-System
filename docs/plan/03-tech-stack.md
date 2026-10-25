# Technology decisions

## Selected stack

| Layer | Decision | Reason and limit |
|---|---|---|
| Runtime | Python 3.13 | One language for backend, detector, demo and evaluation; verify package compatibility at kickoff |
| Web backend | Flask, app factory and blueprints | Familiar to this project; explicit small modules; validation/security must be added deliberately |
| UI | Jinja templates, local CSS, vanilla JavaScript | Avoid a second build pipeline within six days; responsive tables and accessible forms first |
| Charts | Simple HTML/CSS summaries initially | Accurate numbers and evidence views outrank chart-library integration; add a locally bundled chart library later if justified |
| Validation | Pydantic v2 strict models | Central event contract, forbidden extra fields, reusable validation; avoid implicit coercion |
| Persistence | SQLite + SQLAlchemy 2 + Alembic | Local reproducibility, explicit transactions and migrations; one platform process and small workload |
| Sessions | Flask signed cookies + Flask-Login | Established session integration; secrets and cookie settings remain our responsibility |
| CSRF | Flask-WTF CSRF protection | Apply to every session-authenticated mutation; bearer ingestion is a narrowly scoped exemption |
| Passwords | Werkzeug scrypt helper | No custom password hashing |
| Rate limits | Flask-Limiter, in-memory local storage | Adequate for a documented single-process demo; replace storage for hosted use |
| Sender | Python queue/thread + requests | Small bounded background sender with visible loss semantics |
| Browser timing | performance.now() and Pointer Events | Monotonic interaction durations; aggregate counts only, no path recording |
| Testing | pytest + Flask test client | Deterministic rules and request-level security tests; optional Playwright smoke test if time remains |
| Quality | Ruff and GitHub Actions | Fast lint/tests on pull requests; no hosted secrets needed for test execution |
| Local serving | Waitress on loopback | Windows-friendly application server; explicit development mode only for coding |
| Configuration | Environment variables, .env.example with placeholders | Separate demo/platform secrets; no committed credentials or databases |

No React requirement, Pandas dependency, Redis, Kafka, Docker requirement, machine learning library, or cloud account in V1. Add a tool only when a stated requirement needs it. A backend-focused security project still demonstrates full-stack ability through the owner interface and separate application integration.

## Dependency policy

At implementation kickoff, install a compatible stable set in a fresh Python 3.13 virtual environment, run a smoke test, and commit an exact lock generated from that environment. Do not copy the existing prototype's pins or invent package versions from this document. Record tested Python patch version and OS. Keep top-level intent in requirements.in and resolved dependencies in requirements.lock. Recreate the environment from the lock in CI.

## Local and future operation

Local platform at `127.0.0.1:5000`, demo at `127.0.0.1:5001`, independent DB files, session cookie names, and secrets. The exact startup CLI will be documented with the implementation; no commands in this plan imply it exists already.

A future hosted release can retain Flask and templates. Move to PostgreSQL when concurrent writes or hosting storage require it; add a durable queue if delivery guarantees matter. Do not promise that changing a DB connection URL alone handles migration. Select hosting after checking then-current limits, persistent disks, TLS and pricing. Free-tier availability is not assumed.

## Reference basis

These are primary technical references checked while preparing the plan; the architectural selections and numerical defaults are our design decisions.

- [Flask security considerations](https://flask.palletsprojects.com/en/stable/web-security/): resource limits, CSRF and cookie/header protections require deliberate configuration.
- [Python 3.13 sqlite3 documentation](https://docs.python.org/3.13/library/sqlite3.html): connection and transaction behavior must be explicit.
- [SQLAlchemy SQLite dialect](https://docs.sqlalchemy.org/en/20/dialects/sqlite.html): SQLite integration has transaction-specific considerations.
- [MDN performance.now](https://developer.mozilla.org/en-US/docs/Web/API/Performance/now): monotonic timing supports elapsed-duration measurement.

These references do not validate our bot heuristics or predict detection accuracy.
