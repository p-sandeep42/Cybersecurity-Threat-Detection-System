"""ThreatWatch application factory. Importing the package never creates database tables."""

import os
from datetime import timedelta
from pathlib import Path

import click
from flask import Flask, jsonify, render_template, request
from werkzeug.exceptions import HTTPException

from platform_app.database import configure_database, migrate_database
from platform_app.extensions import csrf, limiter, login_manager


def create_app(test_config=None):
    app = Flask(__name__, instance_relative_config=True)
    Path(app.instance_path).mkdir(parents=True, exist_ok=True)
    app.config.from_mapping(
        SECRET_KEY=os.environ.get("THREATWATCH_SECRET"),
        DATABASE_URL=os.environ.get(
            "THREATWATCH_DATABASE",
            f"sqlite:///{Path(app.instance_path) / 'threatwatch.db'}",
        ),
        MAX_CONTENT_LENGTH=16384,
        SESSION_COOKIE_NAME="threatwatch_owner",
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=os.environ.get("THREATWATCH_HTTPS") == "1",
        PERMANENT_SESSION_LIFETIME=timedelta(hours=1),
        SESSION_REFRESH_EACH_REQUEST=False,
        RATELIMIT_ENABLED=True,
    )
    if test_config:
        app.config.update(test_config)
    if not app.config.get("SECRET_KEY") or len(app.config["SECRET_KEY"]) < 32:
        raise RuntimeError("Set THREATWATCH_SECRET to a random secret of at least 32 characters.")
    configure_database(app)
    csrf.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = "auth.login"
    limiter.init_app(app)

    from platform_app.auth import bp as auth_bp
    from platform_app.auth import create_owner
    from platform_app.dashboard import bp as dashboard_bp
    from platform_app.ingestion import bp as ingestion_bp
    from platform_app.receipts import record_outcome
    from platform_app.retention import purge_data

    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(ingestion_bp)
    app.cli.add_command(create_owner)
    app.cli.add_command(purge_data)
    app.after_request(record_outcome)

    @app.cli.command("init-db")
    def init_db():
        """Apply explicit database migrations without deleting existing data."""
        migrate_database()
        click.echo("Database migrations applied.")

    @app.errorhandler(HTTPException)
    def http_error(error):
        if request.path.startswith("/api/"):
            response = jsonify(
                error={
                    "code": error.name.lower().replace(" ", "_"),
                    "message": error.description,
                    "fields": [],
                }
            )
            response.status_code = error.code
        else:
            response = app.make_response((render_template("error.html", error=error), error.code))
        if error.code == 429:
            response.headers["Retry-After"] = "60"
        return response

    @app.after_request
    def security_headers(response):
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; style-src 'self'; script-src 'self'; "
            "frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
        )
        return response

    @app.context_processor
    def pagination_helpers():
        def page_url(number):
            arguments = request.args.to_dict()
            arguments["page"] = number
            from flask import url_for

            return url_for(request.endpoint, **request.view_args, **arguments)

        return {"page_url": page_url}

    return app
