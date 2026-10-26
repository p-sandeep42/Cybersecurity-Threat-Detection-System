"""Add delivery outcome counters without changing existing events or investigations."""

import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"


def upgrade():
    op.create_index("ix_event_session_time", "events", ["app_id", "session_id", "occurred_at"])
    op.create_table(
        "ingestion_receipts",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column(
            "app_id",
            sa.String(),
            sa.ForeignKey("applications.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("received_at", sa.String(), nullable=False),
        sa.Column("outcome", sa.String(), nullable=False),
        sa.Column("http_status", sa.Integer(), nullable=False),
    )
    op.create_index("ix_receipt_app_time", "ingestion_receipts", ["app_id", "received_at"])


def downgrade():
    op.drop_table("ingestion_receipts")
    op.drop_index("ix_event_session_time", table_name="events")
