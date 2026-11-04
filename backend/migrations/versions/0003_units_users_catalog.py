"""Unidades com salas, usuários com perfis e catálogo Inmetro de condicionadores de ar."""

import sqlalchemy as sa
from alembic import op

from app.catalog import read_catalog

revision = "0003_units_users_catalog"
down_revision = "0002_room_management"
branch_labels = None
depends_on = None

DEFAULT_UNIT_ID = "unidade-principal"
DEFAULT_UNIT_NAME = "Unidade principal"


def upgrade():
    op.create_table(
        "units",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("address", sa.String(160), nullable=False, server_default=""),
        sa.UniqueConstraint("name", name="uq_units_name"),
    )
    # Localizações já informadas viram unidades; salas sem localização vão para a principal.
    op.execute("""
        INSERT INTO units (id, name)
        SELECT 'unidade-' || substr(md5(name), 1, 16), name
        FROM (SELECT DISTINCT btrim(location) AS name FROM rooms WHERE btrim(location) <> '') AS f
    """)
    op.execute(f"""
        INSERT INTO units (id, name)
        SELECT '{DEFAULT_UNIT_ID}', '{DEFAULT_UNIT_NAME}'
        WHERE EXISTS (SELECT 1 FROM rooms WHERE btrim(location) = '')
        ON CONFLICT (name) DO NOTHING
    """)
    op.add_column("rooms", sa.Column("unit_id", sa.String(64), nullable=True))
    op.execute("""
        UPDATE rooms SET unit_id = units.id, location = ''
        FROM units WHERE btrim(rooms.location) <> '' AND units.name = btrim(rooms.location)
    """)
    op.execute(f"""
        UPDATE rooms SET unit_id = (SELECT id FROM units WHERE name = '{DEFAULT_UNIT_NAME}')
        WHERE unit_id IS NULL
    """)
    op.alter_column("rooms", "unit_id", nullable=False)
    op.create_foreign_key("fk_rooms_unit_id", "rooms", "units", ["unit_id"], ["id"])
    op.create_index("ix_rooms_unit_id", "rooms", ["unit_id"])
    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("username", sa.String(60), nullable=False),
        sa.Column("full_name", sa.String(120), nullable=False),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column("password_hash", sa.String(200), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint("username", name="uq_users_username"),
        sa.CheckConstraint("role IN ('admin', 'professor')", name="ck_user_role"),
    )
    catalog = op.create_table(
        "ac_catalog",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("brand", sa.String(80), nullable=False),
        sa.Column("model", sa.String(120), nullable=False),
        sa.Column("kind", sa.String(20), nullable=False),
        sa.Column("indoor_unit", sa.String(80), nullable=False),
        sa.Column("outdoor_unit", sa.String(80), nullable=False),
        sa.Column("function", sa.String(20), nullable=False),
        sa.Column("voltage", sa.String(40), nullable=False),
        sa.Column("inverter", sa.Boolean(), nullable=False),
        sa.Column("refrigerant", sa.String(20), nullable=False),
        sa.Column("capacity_btu", sa.Integer(), nullable=False),
        sa.Column("idrs", sa.Float(), nullable=True),
        sa.Column("annual_kwh", sa.Float(), nullable=True),
        sa.Column("energy_class", sa.String(2), nullable=False),
        sa.Column("registration", sa.String(20), nullable=False),
        sa.Column("corrected", sa.Boolean(), nullable=False),
    )
    op.create_index("ix_ac_catalog_brand_kind", "ac_catalog", ["brand", "kind"])
    op.bulk_insert(catalog, read_catalog())


def downgrade():
    op.drop_index("ix_ac_catalog_brand_kind", "ac_catalog")
    op.drop_table("ac_catalog")
    op.drop_table("users")
    op.execute(f"""
        UPDATE rooms SET location = units.name FROM units
        WHERE rooms.unit_id = units.id AND rooms.location = '' AND units.id <> '{DEFAULT_UNIT_ID}'
    """)
    op.drop_index("ix_rooms_unit_id", "rooms")
    op.drop_constraint("fk_rooms_unit_id", "rooms", type_="foreignkey")
    op.drop_column("rooms", "unit_id")
    op.drop_table("units")
