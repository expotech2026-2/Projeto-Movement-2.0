"""Último contato e diagnóstico do ESP32 (Wi-Fi, tempo ligado, sensores, ar-condicionado)."""

import sqlalchemy as sa
from alembic import op

revision = "0007_device_status"
down_revision = "0006_room_control"
branch_labels = None
depends_on = None

COLUMNS = {
    "last_seen_at": lambda: sa.DateTime(timezone=True),
    "firmware": lambda: sa.String(32),
    "rssi": sa.Integer,
    "uptime_seconds": sa.BigInteger,
    "sensor_faults": lambda: sa.String(120),
    "ac_state": lambda: sa.String(60),
}


def upgrade():
    for name, column_type in COLUMNS.items():
        op.add_column("devices", sa.Column(name, column_type(), nullable=True))


def downgrade():
    for name in reversed(COLUMNS):
        op.drop_column("devices", name)
