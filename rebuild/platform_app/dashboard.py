"""Owner-scoped views. Every resource lookup checks ownership before reading data."""

import math
import secrets
from datetime import UTC, datetime, timedelta

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy import delete, func, select, update

from platform_app.database import get_db
from platform_app.ingestion import key_digest
from platform_app.models import (
    Alert,
    AlertEvent,
    ApiKey,
    Application,
    AuditEntry,
    Event,
    Note,
    utc_now,
)

bp = Blueprint("dashboard", __name__)
STATUSES = ("Open", "Investigating", "Resolved")


def owned_application(app_id):
    application = get_db().scalar(
        select(Application).where(
            Application.id == app_id,
            Application.owner_id == current_user.id,
        )
    )
    if application is None:
        abort(404)
    return application


def issue_key(database, application):
    secret = secrets.token_urlsafe(32)
    database.add(ApiKey(app_id=application.id, digest=key_digest(secret), prefix=secret[:8]))
    database.add(
        AuditEntry(
            app_id=application.id,
            actor_id=current_user.id,
            target_id=application.id,
            action="Issued ingestion key",
        )
    )
    return secret


def time_range():
    now = datetime.now(UTC)
    try:
        start = (
            datetime.fromisoformat(request.args["from"])
            if request.args.get("from")
            else (now - timedelta(hours=24))
        )
        end = datetime.fromisoformat(request.args["to"]) if request.args.get("to") else now
        if start.tzinfo is None or end.tzinfo is None:
            raise ValueError
        if start > end or end - start > timedelta(days=7):
            raise ValueError
    except ValueError:
        abort(400, "Use offset-aware ISO timestamps and a range of at most seven days.")
    return start.astimezone(UTC).isoformat(timespec="microseconds"), end.astimezone(UTC).isoformat(
        timespec="microseconds"
    )


def page_number():
    try:
        page = int(request.args.get("page", "1"))
        if page < 1 or page > 100000:
            raise ValueError
        return page
    except ValueError:
        abort(400, "Page must be a positive integer.")


def filtered_events(app_id, start, end):
    query = select(Event).where(Event.app_id == app_id, Event.occurred_at.between(start, end))
    for argument, column in (
        ("subject", Event.subject_id),
        ("ip", Event.source_ip),
        ("outcome", Event.outcome),
    ):
        if request.args.get(argument):
            query = query.where(column == request.args[argument])
    return query


def filtered_alerts(app_id, start, end):
    query = select(Alert).where(Alert.app_id == app_id, Alert.episode_end.between(start, end))
    for argument, column in (
        ("status", Alert.status),
        ("severity", Alert.severity),
        ("rule", Alert.rule_id),
    ):
        if request.args.get(argument):
            query = query.where(column == request.args[argument])
    for argument, column in (("subject", Event.subject_id), ("ip", Event.source_ip)):
        if request.args.get(argument):
            evidence_ids = (
                select(AlertEvent.alert_id)
                .join(Event)
                .where(
                    Event.app_id == app_id,
                    column == request.args[argument],
                )
            )
            query = query.where(Alert.id.in_(evidence_ids))
    return query


@bp.get("/")
def index():
    return redirect(url_for("dashboard.applications"))


@bp.route("/applications", methods=["GET", "POST"])
@login_required
def applications():
    database = get_db()
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        if not 1 <= len(name) <= 80:
            abort(400, "Application name must be 1–80 characters.")
        application = Application(owner_id=current_user.id, name=name)
        database.add(application)
        database.flush()
        secret = issue_key(database, application)
        database.commit()
        return render_template("setup.html", application=application, secret=secret, keys=[])
    records = database.scalars(
        select(Application)
        .where(
            Application.owner_id == current_user.id,
        )
        .order_by(Application.created_at.desc())
    ).all()
    return render_template("applications.html", applications=records)


@bp.get("/applications/<app_id>/setup")
@login_required
def setup(app_id):
    application = owned_application(app_id)
    keys = (
        get_db()
        .scalars(
            select(ApiKey)
            .where(ApiKey.app_id == app_id)
            .order_by(
                ApiKey.created_at.desc(),
            )
        )
        .all()
    )
    return render_template("setup.html", application=application, secret=None, keys=keys)


@bp.post("/applications/<app_id>/keys/<action>")
@login_required
def manage_keys(app_id, action):
    application = owned_application(app_id)
    if action not in {"rotate", "revoke"} or request.form.get("confirm") != "yes":
        abort(400, "Confirm the key operation.")
    database = get_db()
    database.execute(
        update(ApiKey)
        .where(
            ApiKey.app_id == app_id,
            ApiKey.revoked_at.is_(None),
        )
        .values(revoked_at=utc_now())
    )
    database.add(
        AuditEntry(
            app_id=app_id,
            actor_id=current_user.id,
            target_id=app_id,
            action="Revoked ingestion keys",
        )
    )
    secret = issue_key(database, application) if action == "rotate" else None
    database.commit()
    if secret:
        return render_template("setup.html", application=application, secret=secret, keys=[])
    flash("Ingestion keys revoked.")
    return redirect(url_for("dashboard.setup", app_id=app_id))


@bp.post("/applications/<app_id>/delete")
@login_required
def delete_application(app_id):
    application = owned_application(app_id)
    if request.form.get("confirm_name") != application.name:
        abort(400, "Type the application name to confirm deletion.")
    database = get_db()
    database.execute(delete(Application).where(Application.id == app_id))
    database.commit()
    flash("Application and its data deleted.")
    return redirect(url_for("dashboard.applications"))


@bp.get("/applications/<app_id>/events")
@login_required
def events(app_id):
    application = owned_application(app_id)
    start, end = time_range()
    page = page_number()
    records = (
        get_db()
        .scalars(
            filtered_events(app_id, start, end)
            .order_by(
                Event.occurred_at.desc(),
                Event.id.desc(),
            )
            .offset((page - 1) * 50)
            .limit(51)
        )
        .all()
    )
    return render_template(
        "events.html",
        application=application,
        events=records[:50],
        has_next=len(records) > 50,
        page=page,
        start=start,
        end=end,
    )


@bp.get("/applications/<app_id>/alerts")
@login_required
def alerts(app_id):
    application = owned_application(app_id)
    start, end = time_range()
    page = page_number()
    records = (
        get_db()
        .scalars(
            filtered_alerts(app_id, start, end)
            .order_by(
                Alert.episode_end.desc(),
                Alert.id.desc(),
            )
            .offset((page - 1) * 50)
            .limit(51)
        )
        .all()
    )
    return render_template(
        "alerts.html",
        application=application,
        alerts=records[:50],
        has_next=len(records) > 50,
        page=page,
        start=start,
        end=end,
    )


@bp.route("/applications/<app_id>/alerts/<alert_id>", methods=["GET", "POST"])
@login_required
def alert_detail(app_id, alert_id):
    application = owned_application(app_id)
    database = get_db()
    alert = database.scalar(select(Alert).where(Alert.id == alert_id, Alert.app_id == app_id))
    if alert is None:
        abort(404)
    if request.method == "POST":
        if request.form.get("action") == "status":
            status = request.form.get("status")
            if status not in STATUSES:
                abort(400, "Invalid alert status.")
            database.add(
                AuditEntry(
                    app_id=app_id,
                    actor_id=current_user.id,
                    target_id=alert_id,
                    action=f"Status: {alert.status} → {status}",
                )
            )
            alert.status = status
        elif request.form.get("action") == "note":
            body = request.form.get("body", "").strip()
            if not 1 <= len(body) <= 2000:
                abort(400, "Note must be 1–2000 characters.")
            database.add(Note(alert_id=alert_id, owner_id=current_user.id, body=body))
        else:
            abort(400, "Unknown action.")
        database.commit()
        return redirect(url_for("dashboard.alert_detail", app_id=app_id, alert_id=alert_id))
    evidence = database.scalars(
        select(Event)
        .join(AlertEvent)
        .where(
            AlertEvent.alert_id == alert_id,
            Event.app_id == app_id,
        )
        .order_by(Event.occurred_at, Event.event_id)
    ).all()
    notes = database.scalars(
        select(Note)
        .where(Note.alert_id == alert_id)
        .order_by(
            Note.created_at,
        )
    ).all()
    audit = database.scalars(
        select(AuditEntry)
        .where(
            AuditEntry.app_id == app_id,
            AuditEntry.target_id == alert_id,
        )
        .order_by(AuditEntry.created_at)
    ).all()
    return render_template(
        "alert.html",
        application=application,
        alert=alert,
        events=evidence,
        notes=notes,
        audit=audit,
        statuses=STATUSES,
    )


def percentile(values, fraction):
    if not values:
        return None
    ordered = sorted(values)
    return round(ordered[math.ceil(fraction * len(ordered)) - 1], 2)


@bp.get("/applications/<app_id>/metrics")
@login_required
def metrics(app_id):
    application = owned_application(app_id)
    start, end = time_range()
    database = get_db()
    records = database.scalars(filtered_events(app_id, start, end)).all()
    incidents = database.scalars(filtered_alerts(app_id, start, end)).all()
    active = [alert for alert in incidents if alert.status != "Resolved"]
    last_received = database.scalar(
        select(func.max(Event.received_at)).where(Event.app_id == app_id)
    )
    durations = [event.response_duration_ms for event in records]
    stats = {
        "Login events": len(records),
        "Failed logins": sum(event.outcome == "failure" for event in records),
        "Attempted accounts": len({event.subject_id for event in records}),
        "Active alerts": len(active),
        "Critical alerts": sum(alert.severity == "Critical" for alert in active),
        "Flagged accounts": len(
            {alert.entity_key for alert in active if alert.rule_id in {"AUTH-001", "AUTH-003"}}
        ),
        "Flagged IPs": len({alert.entity_key for alert in active if alert.rule_id == "AUTH-002"}),
    }
    return render_template(
        "metrics.html",
        application=application,
        stats=stats,
        start=start,
        end=end,
        last_received=last_received,
        sample_count=len(durations),
        p50=percentile(durations, 0.5),
        p95=percentile(durations, 0.95),
    )
