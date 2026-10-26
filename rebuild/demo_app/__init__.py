"""A separate synthetic bookstore login, instrumented through the public event API."""

import atexit
import hashlib
import hmac
import json
import os
import time
from datetime import UTC, datetime
from uuid import uuid4

from flask import Flask, abort, flash, jsonify, redirect, render_template, request, session, url_for
from flask_wtf.csrf import CSRFProtect
from pydantic import ValidationError
from werkzeug.security import check_password_hash, generate_password_hash

from demo_app.sender import EventSender
from platform_app.schemas import Interaction


def create_app(test_config=None):
    app = Flask(__name__)
    app.config.from_mapping(
        SECRET_KEY=os.environ.get("DEMO_SECRET"),
        DEMO_PASSWORD=os.environ.get("DEMO_PASSWORD"),
        INGESTION_KEY=os.environ.get("THREATWATCH_INGESTION_KEY"),
        PLATFORM_URL=os.environ.get("THREATWATCH_URL", "http://127.0.0.1:5000"),
        SESSION_COOKIE_NAME="threatwatch_demo",
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=os.environ.get("THREATWATCH_HTTPS") == "1",
        MAX_CONTENT_LENGTH=4096,
        START_SENDER=True,
    )
    if test_config:
        app.config.update(test_config)
    if not app.config["SECRET_KEY"] or len(app.config["SECRET_KEY"]) < 32:
        raise RuntimeError("Set DEMO_SECRET to a separate random secret of at least 32 characters.")
    if not app.config["DEMO_PASSWORD"] or len(app.config["DEMO_PASSWORD"]) < 12:
        raise RuntimeError("Set DEMO_PASSWORD to at least 12 characters.")
    if not app.config["INGESTION_KEY"]:
        raise RuntimeError("Set THREATWATCH_INGESTION_KEY from the owner dashboard.")
    password_hash = generate_password_hash(app.config["DEMO_PASSWORD"], method="scrypt")
    CSRFProtect(app)
    sender = EventSender(app.config["PLATFORM_URL"], app.config["INGESTION_KEY"])
    app.extensions["event_sender"] = sender
    if app.config["START_SENDER"]:
        sender.start()
        atexit.register(sender.stop)

    @app.before_request
    def request_clock():
        from flask import g

        g.request_started = time.perf_counter()

    @app.route("/", methods=["GET"])
    @app.route("/login", methods=["GET", "POST"])
    def login():
        now = time.time()
        if now - session.get("last_seen", 0) > 1800 or "telemetry_id" not in session:
            session["telemetry_id"] = str(uuid4())
        session["last_seen"] = now
        if request.method == "POST":
            from flask import g

            username = request.form.get("username", "").strip().lower()
            password = request.form.get("password", "")
            password_valid = check_password_hash(password_hash, password)
            success = username == "reader" and password_valid
            # Client data can supply context, never the outcome or account identity.
            # Invalid telemetry is omitted; authentication must still work.
            interaction = None
            raw_summary = request.form.get("interaction", "")
            if raw_summary:
                try:
                    interaction = Interaction.model_validate(json.loads(raw_summary)).model_dump()
                except (ValueError, ValidationError):
                    app.logger.warning("Invalid browser summary omitted from demo login event")
            if success:
                session["signed_in"] = True
            else:
                session.pop("signed_in", None)
            subject = hmac.new(
                app.config["SECRET_KEY"].encode(),
                username.encode(),
                hashlib.sha256,
            ).hexdigest()
            event = {
                "schema_version": 1,
                "event_id": str(uuid4()),
                "occurred_at": datetime.now(UTC).isoformat(timespec="microseconds"),
                "event_type": "login",
                "outcome": "success" if success else "failure",
                "subject_id": subject,
                "source_ip": request.remote_addr,
                "session_id": session["telemetry_id"],
                "route": "/login",
                "response_duration_ms": round((time.perf_counter() - g.request_started) * 1000, 2),
                "interaction": interaction,
            }
            sender.enqueue(event)
            flash("Signed in successfully." if success else "Invalid username or password.")
            return redirect(url_for("login"))
        return render_template("login.html", signed_in=session.get("signed_in", False))

    @app.post("/logout")
    def logout():
        session.clear()
        return redirect(url_for("login"))

    def require_local_operator():
        # Aggregate sender diagnostics are for a signed-in local demo operator.
        # Never trust forwarded headers for this boundary.
        from ipaddress import ip_address

        if not session.get("signed_in") or not ip_address(request.remote_addr).is_loopback:
            abort(403)

    @app.get("/monitoring")
    def monitoring():
        require_local_operator()
        return render_template(
            "monitoring.html",
            counters=sender.snapshot(),
            queue_size=sender.queue.qsize(),
            worker_alive=bool(sender.worker and sender.worker.is_alive()),
        )

    @app.get("/monitoring/status")
    def monitoring_status():
        require_local_operator()
        return jsonify(
            counters=sender.snapshot(),
            queue_size=sender.queue.qsize(),
            worker_alive=bool(sender.worker and sender.worker.is_alive()),
        )

    @app.cli.command("sender-info")
    def sender_info():
        """Explain counter visibility; a separate CLI process has a separate queue."""
        import click

        click.echo(
            "Delivery failures are logged by the running server. Counters are process-local."
        )

    @app.after_request
    def secure_response(response):
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; style-src 'self'; form-action 'self'; frame-ancestors 'none'"
        )
        return response

    return app
