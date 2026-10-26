"""Request-local sessions and explicit, versioned database initialization."""

from pathlib import Path

from alembic import command
from alembic.config import Config
from flask import current_app, g
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session


def configure_database(app):
    engine = create_engine(app.config["DATABASE_URL"], connect_args={"timeout": 5})

    @event.listens_for(engine, "connect")
    def configure_sqlite(connection, _record):
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("PRAGMA journal_mode=WAL")

    app.extensions["database_engine"] = engine

    @app.teardown_appcontext
    def close_session(_error):
        database = g.pop("database", None)
        if database is not None:
            database.close()


def get_db() -> Session:
    if "database" not in g:
        g.database = Session(current_app.extensions["database_engine"], expire_on_commit=False)
    return g.database


def migrate_database():
    config = Config()
    config.set_main_option("script_location", str(Path(__file__).parents[1] / "migrations"))
    with current_app.extensions["database_engine"].begin() as connection:
        config.attributes["connection"] = connection
        command.upgrade(config, "head")
