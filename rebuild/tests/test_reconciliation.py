from sqlalchemy import select

from platform_app.database import get_db
from platform_app.models import Alert, AlertEvent, AuditEntry, Note
from tests.helpers import send_event


def test_late_bridge_merges_incidents_and_preserves_notes(client, app, event_factory):
    # Neither initial cluster sees the other within five minutes.
    for second in (*range(5), *range(600, 605)):
        assert send_event(client, event_factory(seconds=second)).status_code == 201
    with app.app_context():
        database = get_db()
        alerts = database.scalars(select(Alert).order_by(Alert.created_at)).all()
        assert len(alerts) == 2
        first_id = alerts[0].id
        from platform_app.models import Application

        owner_id = database.get(Application, app.config["TEST_APP_ID"]).owner_id
        for index, alert in enumerate(alerts):
            alert.status = "Resolved"
            database.add(Note(alert_id=alert.id, owner_id=owner_id, body=f"note-{index}"))
        database.commit()
    # Five late events bridge both clusters through overlapping qualifying windows.
    for second in range(300, 305):
        assert send_event(client, event_factory(seconds=second)).status_code == 201
    with app.app_context():
        database = get_db()
        alerts = database.scalars(select(Alert)).all()
        assert len(alerts) == 1
        assert alerts[0].id == first_id
        assert alerts[0].status == "Open"
        assert len(database.scalars(select(Note).where(Note.alert_id == first_id)).all()) == 2
        assert len(database.scalars(select(AlertEvent)).all()) == 15
        assert any("Merged" in entry.action for entry in database.scalars(select(AuditEntry)))
