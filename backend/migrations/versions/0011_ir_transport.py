"""Seleção entre o emissor do ESP32 e o gateway Xiaomi."""

import sqlalchemy as sa
from alembic import op

revision = "0011_ir_transport"
down_revision = "0010_ir_brand_candidate"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "rooms", sa.Column("ir_transport", sa.String(10), nullable=False, server_default="esp32")
    )
    op.add_column(
        "rooms", sa.Column("ir_gateway_url", sa.String(100), nullable=False, server_default="")
    )
    op.add_column(
        "rooms",
        sa.Column("ir_transport_revision", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_check_constraint(
        "ck_room_ir_transport", "rooms", "ir_transport IN ('esp32', 'xiaomi')"
    )


def downgrade():
    op.drop_constraint("ck_room_ir_transport", "rooms", type_="check")
    op.drop_column("rooms", "ir_transport_revision")
    op.drop_column("rooms", "ir_gateway_url")
    op.drop_column("rooms", "ir_transport")
