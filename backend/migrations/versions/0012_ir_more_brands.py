"""Candidatos de protocolo para Elgin, Agratto e Philco nos aparelhos que ficaram pendentes."""

import sqlalchemy as sa
from alembic import op

revision = "0012_ir_more_brands"
down_revision = "0011_ir_transport"
branch_labels = None
depends_on = None

# Cópia estável das marcas novas de app.ir_protocols.BRAND_PROTOCOLS na data desta migração.
BRAND_PROTOCOLS = {
    "ELGIN": ("COOLIX", 1),
    "AGRATTO": ("TCL112AC", 1),
    "PHILCO": ("MIRAGE", 1),
}
NORMALIZED_BRAND = "regexp_replace(upper(brand), '[^A-Z0-9]', '', 'g')"


def upgrade():
    for brand, (protocol, ir_model) in BRAND_PROTOCOLS.items():
        op.get_bind().execute(
            sa.text(
                "UPDATE air_conditioners SET ir_protocol=:protocol, ir_model=:ir_model, "
                "ir_source='brand_candidate' "
                f"WHERE ir_protocol IS NULL AND {NORMALIZED_BRAND} = :brand"
            ),
            {"protocol": protocol, "ir_model": ir_model, "brand": brand},
        )


def downgrade():
    op.get_bind().execute(
        sa.text(
            "UPDATE air_conditioners SET ir_protocol=NULL, ir_model=1, ir_source='pending' "
            f"WHERE ir_source='brand_candidate' AND {NORMALIZED_BRAND} IN :brands"
        ).bindparams(sa.bindparam("brands", expanding=True)),
        {"brands": list(BRAND_PROTOCOLS)},
    )
