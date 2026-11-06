"""Alertas de conforto e umidade gerados pela telemetria."""

import sqlalchemy as sa
from alembic import op

revision = "0005_alerts"
down_revision = "0004_user_session_version"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "alerts",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("room_id", sa.String(64), sa.ForeignKey("rooms.id"), nullable=False),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("message", sa.String(200), nullable=False),
        sa.Column("value", sa.Float(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint("kind IN ('conforto', 'umidade')", name="ck_alert_kind"),
    )
    op.create_index("ix_alerts_room_created", "alerts", ["room_id", "created_at"])


def downgrade():
    op.drop_index("ix_alerts_room_created", "alerts")
    op.drop_table("alerts")
