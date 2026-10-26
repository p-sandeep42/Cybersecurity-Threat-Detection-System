"""Reconcile deterministic incidents while preserving human investigation work."""

from sqlalchemy import delete, or_, select, update

from platform_app.detection import evaluate
from platform_app.models import Alert, AlertEvent, AuditEntry, Event, Note


def reconcile(database, app_id: str, incoming: Event) -> list[str]:
    # Recompute only the affected subject/IP scopes. Do not mix applications.
    events = list(
        database.scalars(
            select(Event).where(
                Event.app_id == app_id,
                or_(Event.subject_id == incoming.subject_id, Event.source_ip == incoming.source_ip),
            )
        )
    )
    relevant = [
        episode
        for episode in evaluate([event.payload for event in events])
        if (
            (
                episode.rule_id in {"AUTH-001", "AUTH-003"}
                and episode.entity_key == incoming.subject_id
            )
            or (episode.rule_id == "AUTH-002" and episode.entity_key == incoming.source_ip)
        )
    ]
    internal_ids = {event.event_id: event.id for event in events}
    affected_ids = []
    for episode in relevant:
        evidence = {internal_ids[event_id] for event_id in episode.evidence}
        matches = list(
            database.scalars(
                select(Alert)
                .join(AlertEvent)
                .where(
                    Alert.app_id == app_id,
                    Alert.rule_id == episode.rule_id,
                    Alert.rule_version == 1,
                    Alert.entity_key == episode.entity_key,
                    AlertEvent.event_id.in_(evidence),
                )
                .distinct()
                .order_by(Alert.created_at, Alert.id)
            )
        )

        if matches:
            alert = matches[0]
            old_evidence = set(
                database.scalars(
                    select(AlertEvent.event_id).where(
                        AlertEvent.alert_id == alert.id,
                    )
                )
            )
            priority = {"Open": 0, "Investigating": 1, "Resolved": 2}
            alert.status = min((match.status for match in matches), key=priority.get)
            for replaced in matches[1:]:
                database.execute(
                    update(Note)
                    .where(Note.alert_id == replaced.id)
                    .values(
                        alert_id=alert.id,
                    )
                )
                database.execute(
                    update(AuditEntry)
                    .where(
                        AuditEntry.app_id == app_id,
                        AuditEntry.target_id == replaced.id,
                    )
                    .values(target_id=alert.id)
                )
                database.add(
                    AuditEntry(
                        app_id=app_id,
                        target_id=alert.id,
                        action=f"Merged incident {replaced.id}",
                    )
                )
                database.delete(replaced)
            if alert.status == "Resolved" and evidence - old_evidence:
                alert.status = "Open"
                database.add(
                    AuditEntry(
                        app_id=app_id,
                        target_id=alert.id,
                        action="Reopened after new evidence",
                    )
                )
            database.execute(delete(AlertEvent).where(AlertEvent.alert_id == alert.id))
        else:
            alert = Alert(app_id=app_id, rule_id=episode.rule_id, entity_key=episode.entity_key)
            database.add(alert)

        alert.episode_start = episode.start
        alert.episode_end = episode.end
        alert.score = episode.score
        alert.severity = episode.severity
        alert.reason = episode.reason
        alert.thresholds = episode.thresholds
        database.flush()
        for event_id in evidence:
            database.add(AlertEvent(alert_id=alert.id, event_id=event_id))
        database.flush()
        if incoming.id in evidence:
            affected_ids.append(alert.id)
    return affected_ids
