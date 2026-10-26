"""Initial schema, frozen independently of future model changes."""

import sqlalchemy as sa
from alembic import op

revision = "0001"
down_revision = None


def upgrade():
    op.create_table(
        "owners",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("login", sa.String(128), nullable=False, unique=True),
        sa.Column("password_hash", sa.String(), nullable=False),
    )
    op.create_table(
        "applications",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("owner_id", sa.String(), sa.ForeignKey("owners.id"), nullable=False),
        sa.Column("name", sa.String(80), nullable=False),
        sa.Column("created_at", sa.String(), nullable=False),
    )
    op.create_index("ix_applications_owner_id", "applications", ["owner_id"])
    op.create_table(
        "api_keys",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column(
            "app_id",
            sa.String(),
            sa.ForeignKey("applications.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("digest", sa.String(), nullable=False, unique=True),
        sa.Column("prefix", sa.String(), nullable=False),
        sa.Column("created_at", sa.String(), nullable=False),
        sa.Column("revoked_at", sa.String()),
    )
    op.create_table(
        "events",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column(
            "app_id",
            sa.String(),
            sa.ForeignKey("applications.id", ondelete="CASCADE"),
            nullable=False,
        ),
        *[
            sa.Column(name, sa.String(), nullable=False)
            for name in (
                "event_id",
                "occurred_at",
                "received_at",
                "subject_id",
                "source_ip",
                "session_id",
                "outcome",
                "payload_hash",
            )
        ],
        sa.Column("response_duration_ms", sa.Float(), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.UniqueConstraint("app_id", "event_id"),
    )
    op.create_index("ix_event_subject_time", "events", ["app_id", "subject_id", "occurred_at"])
    op.create_index("ix_event_ip_time", "events", ["app_id", "source_ip", "occurred_at"])
    op.create_table(
        "alerts",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column(
            "app_id",
            sa.String(),
            sa.ForeignKey("applications.id", ondelete="CASCADE"),
            nullable=False,
        ),
        *[
            sa.Column(name, sa.String(), nullable=False)
            for name in (
                "rule_id",
                "entity_key",
                "episode_start",
                "episode_end",
                "severity",
                "reason",
                "status",
                "created_at",
            )
        ],
        sa.Column("rule_version", sa.Integer(), nullable=False),
        sa.Column("score", sa.Integer(), nullable=False),
        sa.Column("thresholds", sa.JSON(), nullable=False),
    )
    op.create_index("ix_alert_status_time", "alerts", ["app_id", "status", "episode_end"])
    op.create_table(
        "alert_events",
        sa.Column(
            "alert_id",
            sa.String(),
            sa.ForeignKey("alerts.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "event_id",
            sa.String(),
            sa.ForeignKey("events.id", ondelete="CASCADE"),
            primary_key=True,
        ),
    )
    op.create_table(
        "notes",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column(
            "alert_id", sa.String(), sa.ForeignKey("alerts.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("owner_id", sa.String(), sa.ForeignKey("owners.id"), nullable=False),
        sa.Column("body", sa.String(2000), nullable=False),
        sa.Column("created_at", sa.String(), nullable=False),
    )
    op.create_table(
        "audit_entries",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column(
            "app_id",
            sa.String(),
            sa.ForeignKey("applications.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("actor_id", sa.String(), sa.ForeignKey("owners.id")),
        sa.Column("target_id", sa.String(), nullable=False),
        sa.Column("action", sa.String(), nullable=False),
        sa.Column("created_at", sa.String(), nullable=False),
    )


def downgrade():
    for table in (
        "audit_entries",
        "notes",
        "alert_events",
        "alerts",
        "events",
        "api_keys",
        "applications",
        "owners",
    ):
        op.drop_table(table)
