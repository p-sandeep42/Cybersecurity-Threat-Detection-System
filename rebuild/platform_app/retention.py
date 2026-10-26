"""Explicit local-admin retention command; preview before applying any deletion."""

from datetime import UTC, datetime, timedelta

import click
from flask.cli import with_appcontext
from sqlalchemy import delete, func, select

from platform_app.database import get_db
from platform_app.models import (
    Alert,
    AlertEvent,
    Application,
    AuditEntry,
    Event,
    IngestionReceipt,
    Note,
)


def purge_before(database, cutoff: str, app_ids: list[str], apply: bool = False) -> dict:
    events = select(Event.id).where(Event.app_id.in_(app_ids), Event.occurred_at < cutoff)
    alerts = select(AlertEvent.alert_id).where(AlertEvent.event_id.in_(events)).distinct()
    conditions = {
        "notes": (Note, Note.alert_id.in_(alerts)),
        "evidence_links": (AlertEvent, AlertEvent.alert_id.in_(alerts)),
        "alerts": (Alert, Alert.id.in_(alerts)),
        "events": (Event, Event.id.in_(events)),
        "audit_entries": (
            AuditEntry,
            AuditEntry.app_id.in_(app_ids)
            & ((AuditEntry.created_at < cutoff) | AuditEntry.target_id.in_(alerts)),
        ),
        "delivery_receipts": (
            IngestionReceipt,
            IngestionReceipt.app_id.in_(app_ids) & (IngestionReceipt.received_at < cutoff),
        ),
    }
    counts = {
        name: database.scalar(select(func.count()).select_from(model).where(condition))
        for name, (model, condition) in conditions.items()
    }
    if apply:
        # Remove audit references while the subquery still has its evidence links;
        # database cascades remove notes and links with their parent alerts.
        for name in ("audit_entries", "alerts", "events", "delivery_receipts"):
            model, condition = conditions[name]
            database.execute(
                delete(model).where(condition).execution_options(synchronize_session=False)
            )
        database.commit()
    return counts


@click.command("purge-data")
@click.option("--application-id", help="Application UUID to purge.")
@click.option("--all-applications", is_flag=True, help="Explicitly select every local application.")
@click.option("--before", help="Offset-aware ISO timestamp; defaults to seven days ago.")
@click.option(
    "--apply", is_flag=True, help="Delete the previewed data. Otherwise only report counts."
)
@with_appcontext
def purge_data(application_id, all_applications, before, apply):
    """Purge old events plus all incidents that depend on them (local administrator only)."""
    if bool(application_id) == all_applications:
        raise click.ClickException("Choose --application-id or --all-applications, not both.")
    now = datetime.now(UTC)
    try:
        cutoff = datetime.fromisoformat(before) if before else now - timedelta(days=7)
        if cutoff.tzinfo is None or cutoff > now:
            raise ValueError
    except ValueError:
        raise click.ClickException(
            "Cutoff must include a timezone and must not be in the future."
        ) from None
    database = get_db()
    query = select(Application.id)
    if application_id:
        query = query.where(Application.id == application_id)
    app_ids = list(database.scalars(query))
    if application_id and not app_ids:
        raise click.ClickException("Application not found.")
    # Serialize preview-and-delete with ingestion, so counts match the deletion.
    database.rollback()
    database.connection().exec_driver_sql("BEGIN IMMEDIATE")
    counts = purge_before(
        database, cutoff.astimezone(UTC).isoformat(timespec="microseconds"), app_ids, apply
    )
    click.echo(f"{'Deleted' if apply else 'Preview only'} — cutoff {cutoff.isoformat()}")
    for name, count in counts.items():
        click.echo(f"{name}: {count}")
    if not apply:
        database.rollback()
        click.echo("Nothing deleted. Add --apply to execute this purge.")
