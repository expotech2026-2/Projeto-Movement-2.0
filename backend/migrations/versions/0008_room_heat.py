"""Computadores e tamanho da sala: o ESP32 soma o calor das máquinas e usa o volume do ar."""

import sqlalchemy as sa
from alembic import op

revision = "0008_room_heat"
down_revision = "0007_device_status"
branch_labels = None
depends_on = None

CHECKS = {
    "ck_room_computers": "computers BETWEEN 0 AND 10000",
    "ck_room_area": "area_m2 IS NULL OR area_m2 BETWEEN 1 AND 100000",
    "ck_room_ceiling": "ceiling_height_m BETWEEN 2 AND 20",
}


def upgrade():
    op.add_column("rooms", sa.Column("computers", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("rooms", sa.Column("area_m2", sa.Float(), nullable=True))
    op.add_column(
        "rooms", sa.Column("ceiling_height_m", sa.Float(), nullable=False, server_default="3")
    )
    for name, condition in CHECKS.items():
        op.create_check_constraint(name, "rooms", condition)


def downgrade():
    for name in reversed(CHECKS):
        op.drop_constraint(name, "rooms", type_="check")
    for column in ("ceiling_height_m", "area_m2", "computers"):
        op.drop_column("rooms", column)
