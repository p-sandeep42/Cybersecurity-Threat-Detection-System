"""Persistent records. All application data belongs to one owner through Application."""

from datetime import UTC, datetime
from uuid import uuid4

from flask_login import UserMixin
from sqlalchemy import JSON, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def new_id() -> str:
    return str(uuid4())


def utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="microseconds")


class Base(DeclarativeBase):
    pass


class Owner(UserMixin, Base):
    __tablename__ = "owners"

    id: Mapped[str] = mapped_column(primary_key=True, default=new_id)
    login: Mapped[str] = mapped_column(String(128), unique=True)
    password_hash: Mapped[str]


class Application(Base):
    __tablename__ = "applications"

    id: Mapped[str] = mapped_column(primary_key=True, default=new_id)
    owner_id: Mapped[str] = mapped_column(ForeignKey("owners.id"), index=True)
    name: Mapped[str] = mapped_column(String(80))
    created_at: Mapped[str] = mapped_column(default=utc_now)


class ApiKey(Base):
    __tablename__ = "api_keys"

    id: Mapped[str] = mapped_column(primary_key=True, default=new_id)
    app_id: Mapped[str] = mapped_column(ForeignKey("applications.id", ondelete="CASCADE"))
    digest: Mapped[str] = mapped_column(unique=True)
    prefix: Mapped[str]
    created_at: Mapped[str] = mapped_column(default=utc_now)
    revoked_at: Mapped[str | None]


class Event(Base):
    __tablename__ = "events"
    __table_args__ = (
        UniqueConstraint("app_id", "event_id"),
        Index("ix_event_subject_time", "app_id", "subject_id", "occurred_at"),
        Index("ix_event_ip_time", "app_id", "source_ip", "occurred_at"),
        Index("ix_event_session_time", "app_id", "session_id", "occurred_at"),
    )

    id: Mapped[str] = mapped_column(primary_key=True, default=new_id)
    app_id: Mapped[str] = mapped_column(ForeignKey("applications.id", ondelete="CASCADE"))
    event_id: Mapped[str]
    occurred_at: Mapped[str]
    received_at: Mapped[str] = mapped_column(default=utc_now)
    subject_id: Mapped[str]
    source_ip: Mapped[str]
    session_id: Mapped[str]
    outcome: Mapped[str]
    response_duration_ms: Mapped[float]
    payload: Mapped[dict] = mapped_column(JSON)
    payload_hash: Mapped[str]


class Alert(Base):
    __tablename__ = "alerts"
    __table_args__ = (Index("ix_alert_status_time", "app_id", "status", "episode_end"),)

    id: Mapped[str] = mapped_column(primary_key=True, default=new_id)
    app_id: Mapped[str] = mapped_column(ForeignKey("applications.id", ondelete="CASCADE"))
    rule_id: Mapped[str]
    rule_version: Mapped[int] = mapped_column(default=1)
    entity_key: Mapped[str]
    episode_start: Mapped[str]
    episode_end: Mapped[str]
    score: Mapped[int]
    severity: Mapped[str]
    reason: Mapped[str]
    thresholds: Mapped[dict] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(default="Open")
    created_at: Mapped[str] = mapped_column(default=utc_now)


class AlertEvent(Base):
    __tablename__ = "alert_events"

    alert_id: Mapped[str] = mapped_column(
        ForeignKey("alerts.id", ondelete="CASCADE"), primary_key=True
    )
    event_id: Mapped[str] = mapped_column(
        ForeignKey("events.id", ondelete="CASCADE"), primary_key=True
    )


class Note(Base):
    __tablename__ = "notes"

    id: Mapped[str] = mapped_column(primary_key=True, default=new_id)
    alert_id: Mapped[str] = mapped_column(ForeignKey("alerts.id", ondelete="CASCADE"))
    owner_id: Mapped[str] = mapped_column(ForeignKey("owners.id"))
    body: Mapped[str] = mapped_column(String(2000))
    created_at: Mapped[str] = mapped_column(default=utc_now)


class AuditEntry(Base):
    __tablename__ = "audit_entries"

    id: Mapped[str] = mapped_column(primary_key=True, default=new_id)
    app_id: Mapped[str] = mapped_column(ForeignKey("applications.id", ondelete="CASCADE"))
    actor_id: Mapped[str | None] = mapped_column(ForeignKey("owners.id"))
    target_id: Mapped[str]
    action: Mapped[str]
    created_at: Mapped[str] = mapped_column(default=utc_now)


class IngestionReceipt(Base):
    """Minimal delivery outcome; deliberately stores no payload, identity or key."""

    __tablename__ = "ingestion_receipts"
    __table_args__ = (Index("ix_receipt_app_time", "app_id", "received_at"),)

    id: Mapped[str] = mapped_column(primary_key=True, default=new_id)
    app_id: Mapped[str] = mapped_column(ForeignKey("applications.id", ondelete="CASCADE"))
    received_at: Mapped[str] = mapped_column(default=utc_now)
    outcome: Mapped[str]
    http_status: Mapped[int]
