"""Isolated local lab: never opens the operator's application database."""

import secrets
from contextlib import contextmanager
from pathlib import Path
from tempfile import TemporaryDirectory

from werkzeug.security import generate_password_hash

from platform_app import create_app
from platform_app.database import get_db, migrate_database
from platform_app.ingestion import key_digest
from platform_app.models import ApiKey, Application, Owner


@contextmanager
def temporary_platform():
    with TemporaryDirectory(prefix="threatwatch-lab-") as directory:
        app = create_app(
            {
                "TESTING": True,
                "SECRET_KEY": secrets.token_hex(32),
                "DATABASE_URL": f"sqlite:///{Path(directory) / 'lab.db'}",
                "RATELIMIT_ENABLED": False,
            }
        )
        key = secrets.token_urlsafe(32)
        with app.app_context():
            migrate_database()
            database = get_db()
            owner = Owner(
                login="lab-owner", password_hash=generate_password_hash("lab-password-only")
            )
            database.add(owner)
            database.flush()
            application = Application(name="Synthetic lab", owner_id=owner.id)
            database.add(application)
            database.flush()
            database.add(ApiKey(app_id=application.id, digest=key_digest(key), prefix=key[:8]))
            database.commit()
            app_id, owner_id = application.id, owner.id
        try:
            yield app, app_id, owner_id, key
        finally:
            app.extensions["database_engine"].dispose()
