"""Salas, inventário de aparelhos e consolidação mensal."""

import sqlalchemy as sa
from alembic import op

revision = "0002_room_management"
down_revision = "0001_telemetry"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("rooms", sa.Column("location", sa.String(120), nullable=False, server_default=""))
    op.add_column("rooms", sa.Column("capacity", sa.Integer(), nullable=False, server_default="1"))
    op.create_check_constraint("ck_room_capacity", "rooms", "capacity BETWEEN 1 AND 10000")
    op.create_table(
        "air_conditioners",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("room_id", sa.String(64), sa.ForeignKey("rooms.id"), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("kind", sa.String(20), nullable=False),
        sa.Column("brand", sa.String(80), nullable=False),
        sa.Column("model", sa.String(80), nullable=False),
        sa.Column("capacity_btu", sa.Integer(), nullable=False),
        sa.Column("inverter", sa.Boolean(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.CheckConstraint("capacity_btu BETWEEN 1000 AND 500000", name="ck_ac_capacity"),
        sa.CheckConstraint(
            "kind IN ('split', 'janela', 'cassete', 'piso_teto', 'portatil', 'vrf')",
            name="ck_ac_kind",
        ),
        sa.CheckConstraint("status IN ('ativo', 'manutencao', 'inativo')", name="ck_ac_status"),
    )
    op.create_index("ix_air_conditioners_room_id", "air_conditioners", ["room_id"])
    columns = [
        sa.Column("room_id", sa.String(64), sa.ForeignKey("rooms.id"), primary_key=True),
        sa.Column("month", sa.Date(), primary_key=True),
        sa.Column("sample_count", sa.BigInteger(), nullable=False),
    ]
    for metric in (
        "temp_inside",
        "temp_outside",
        "humidity_inside",
        "humidity_outside",
        "occupancy",
        "ac_on",
    ):
        columns.append(sa.Column(f"{metric}_sum", sa.Float(), nullable=False))
        name = "ac_on_percent" if metric == "ac_on" else f"avg_{metric}"
        expression = f"{'100.0 * ' if metric == 'ac_on' else ''}{metric}_sum / sample_count"
        columns.append(
            sa.Column(name, sa.Float(), sa.Computed(expression, persisted=True), nullable=False)
        )
    op.create_table(
        "monthly_summaries",
        *columns,
        sa.CheckConstraint("sample_count > 0", name="ck_summary_count"),
    )
    op.create_index("ix_readings_measured", "sensor_readings", ["measured_at"])


def downgrade():
    op.drop_index("ix_readings_measured", "sensor_readings")
    op.drop_table("monthly_summaries")
    op.drop_table("air_conditioners")
    op.drop_constraint("ck_room_capacity", "rooms")
    op.drop_column("rooms", "capacity")
    op.drop_column("rooms", "location")
