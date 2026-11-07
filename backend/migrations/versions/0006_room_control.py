"""Cidade da unidade (temperatura externa) e comando do ar-condicionado pelo site."""

import sqlalchemy as sa
from alembic import op

revision = "0006_room_control"
down_revision = "0005_alerts"
branch_labels = None
depends_on = None

ROOM_COLUMNS = ("ac_mode", "ac_target", "ac_version", "ac_changed_by", "ac_changed_at")


def upgrade():
    op.add_column("units", sa.Column("city", sa.String(120), nullable=False, server_default=""))
    op.add_column("units", sa.Column("latitude", sa.Float(), nullable=True))
    op.add_column("units", sa.Column("longitude", sa.Float(), nullable=True))
    op.add_column(
        "rooms", sa.Column("ac_mode", sa.String(10), nullable=False, server_default="auto")
    )
    op.add_column("rooms", sa.Column("ac_target", sa.Integer(), nullable=True))
    op.add_column(
        "rooms", sa.Column("ac_version", sa.Integer(), nullable=False, server_default="0")
    )
    op.add_column("rooms", sa.Column("ac_changed_by", sa.String(60), nullable=True))
    op.add_column("rooms", sa.Column("ac_changed_at", sa.DateTime(timezone=True), nullable=True))
    op.create_check_constraint("ck_room_ac_mode", "rooms", "ac_mode IN ('auto', 'manual', 'off')")
    op.create_check_constraint(
        "ck_room_ac_target", "rooms", "ac_target IS NULL OR ac_target BETWEEN 16 AND 30"
    )


def downgrade():
    op.drop_constraint("ck_room_ac_target", "rooms", type_="check")
    op.drop_constraint("ck_room_ac_mode", "rooms", type_="check")
    for column in reversed(ROOM_COLUMNS):
        op.drop_column("rooms", column)
    for column in ("longitude", "latitude", "city"):
        op.drop_column("units", column)
