"""Protocolo por aparelho e preenchimento por correspondência de modelo."""

import sqlalchemy as sa
from alembic import op

revision = "0009_appliance_ir"
down_revision = "0008_room_heat"
branch_labels = None
depends_on = None


MODEL_PROTOCOLS = [
    {
        "brand": "LG",
        "model": "S4-W12JA3AA",
        "protocol": "LG2",
        "ir_model": 2,
        "confidence": "model_documented",
    },
    {
        "brand": "LG",
        "model": "TS-H122ERM1",
        "protocol": "LG",
        "ir_model": 5,
        "confidence": "model_documented",
    },
    {
        "brand": "LG",
        "model": "AMNW09GSJA0",
        "protocol": "LG2",
        "ir_model": 3,
        "confidence": "model_documented",
    },
    {
        "brand": "LG",
        "model": "AMNW24GTPA1",
        "protocol": "LG2",
        "ir_model": 4,
        "confidence": "model_documented",
    },
    {
        "brand": "LG",
        "model": "MS05SQ NW0",
        "protocol": "LG2",
        "ir_model": 3,
        "confidence": "model_documented",
    },
    {
        "brand": "GREE",
        "model": "VIR09HP115V1AH",
        "protocol": "GREE",
        "ir_model": 1,
        "confidence": "model_documented",
    },
    {
        "brand": "GREE",
        "model": "VIR12HP230V1AH",
        "protocol": "GREE",
        "ir_model": 1,
        "confidence": "model_documented",
    },
    {
        "brand": "MIDEA",
        "model": "MS12FU-10HRDN1-QRD0GW(B)",
        "protocol": "COOLIX",
        "ir_model": 1,
        "confidence": "model_documented",
    },
    {
        "brand": "MIDEA",
        "model": "MSABAU-07HRFN1-QRD0GW",
        "protocol": "COOLIX",
        "ir_model": 1,
        "confidence": "model_documented",
    },
    {
        "brand": "SAMSUNG",
        "model": "AR24BVFAAWKNAZ",
        "protocol": "SAMSUNG_AC",
        "ir_model": 1,
        "confidence": "family_candidate",
    },
]


def upgrade():
    connection = op.get_bind()
    columns = {item["name"] for item in sa.inspect(connection).get_columns("air_conditioners")}
    additions = [
        sa.Column("ir_protocol", sa.String(32), nullable=True),
        sa.Column("ir_model", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("ir_source", sa.String(32), nullable=False, server_default="pending"),
    ]
    for column in additions:
        if column.name not in columns:
            op.add_column("air_conditioners", column)
    room_columns = {item["name"] for item in sa.inspect(connection).get_columns("rooms")}
    if "ir_revision" not in room_columns:
        op.add_column(
            "rooms", sa.Column("ir_revision", sa.Integer(), nullable=False, server_default="0")
        )
    for row in MODEL_PROTOCOLS:
        op.get_bind().execute(
            sa.text(
                "UPDATE air_conditioners SET ir_protocol=:protocol, ir_model=:ir_model, "
                "ir_source=:confidence WHERE ir_protocol IS NULL AND "
                "regexp_replace(upper(brand), '[^A-Z0-9]', '', 'g') = "
                "regexp_replace(upper(:brand), '[^A-Z0-9]', '', 'g') AND "
                "regexp_replace(upper(model), '[^A-Z0-9]', '', 'g') = "
                "regexp_replace(upper(:model), '[^A-Z0-9]', '', 'g')"
            ),
            row,
        )


def downgrade():
    op.drop_column("rooms", "ir_revision")
    for name in ("ir_source", "ir_model", "ir_protocol"):
        op.drop_column("air_conditioners", name)
