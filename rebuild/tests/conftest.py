from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from werkzeug.security import generate_password_hash

from platform_app import create_app
from platform_app.database import get_db, migrate_database
from platform_app.ingestion import key_digest
from platform_app.models import ApiKey, Application, Owner


@pytest.fixture
def app(tmp_path):
    application = create_app(
        {
            "TESTING": True,
            "SECRET_KEY": "test-only-secret-" * 4,
            "DATABASE_URL": f"sqlite:///{tmp_path / 'test.db'}",
            "RATELIMIT_ENABLED": False,
        }
    )
    with application.app_context():
        migrate_database()
        database = get_db()
        owner = Owner(login="owner", password_hash=generate_password_hash("test-password-123"))
        stranger = Owner(
            login="stranger", password_hash=generate_password_hash("other-password-123")
        )
        database.add_all([owner, stranger])
        database.flush()
        project = Application(name="Bookstore", owner_id=owner.id)
        other = Application(name="Private project", owner_id=stranger.id)
        database.add_all([project, other])
        database.flush()
        database.add_all(
            [
                ApiKey(app_id=project.id, digest=key_digest("test-key"), prefix="test-key"),
                ApiKey(app_id=other.id, digest=key_digest("other-key"), prefix="other-key"),
            ]
        )
        database.commit()
        application.config["TEST_APP_ID"] = project.id
        application.config["OTHER_APP_ID"] = other.id
    yield application
    application.extensions["database_engine"].dispose()


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def event_factory():
    base_time = datetime.now(UTC) - timedelta(hours=1)

    def make_event(seconds=0, **changes):
        event = {
            "schema_version": 1,
            "event_id": str(uuid4()),
            "occurred_at": (base_time + timedelta(seconds=seconds)).isoformat(
                timespec="microseconds"
            ),
            "event_type": "login",
            "outcome": "failure",
            "subject_id": "account-1",
            "source_ip": "203.0.113.42",
            "session_id": str(uuid4()),
            "route": "/login",
            "response_duration_ms": 42.5,
            "interaction": None,
        }
        event.update(changes)
        return event

    return make_event
