"""Protocolo candidato pela marca para os aparelhos que ficaram pendentes."""

import sqlalchemy as sa
from alembic import op

revision = "0010_ir_brand_candidate"
down_revision = "0009_appliance_ir"
branch_labels = None
depends_on = None

# Cópia estável de app.ir_protocols.BRAND_PROTOCOLS na data desta migração.
BRAND_PROTOCOLS = {
    "LG": ("LG2", 2),
    "GREE": ("GREE", 1),
    "SAMSUNG": ("SAMSUNG_AC", 1),
    "MIDEA": ("COOLIX", 1),
    "SPRINGER": ("COOLIX", 1),
    "SPRINGERMIDEA": ("COOLIX", 1),
    "CARRIER": ("COOLIX", 1),
    "TCL": ("TCL112AC", 1),
    "DAIKIN": ("DAIKIN", 1),
    "FUJITSU": ("FUJITSU_AC", 1),
    "FUJITSUAIRSTAGE": ("FUJITSU_AC", 1),
    "AIRSTAGE": ("FUJITSU_AC", 1),
    "HITACHI": ("HITACHI_AC", 1),
    "CONSUL": ("WHIRLPOOL_AC", 1),
    "BRASTEMP": ("WHIRLPOOL_AC", 1),
}


def upgrade():
    for brand, (protocol, ir_model) in BRAND_PROTOCOLS.items():
        op.get_bind().execute(
            sa.text(
                "UPDATE air_conditioners SET ir_protocol=:protocol, ir_model=:ir_model, "
                "ir_source='brand_candidate' WHERE ir_protocol IS NULL AND "
                "regexp_replace(upper(brand), '[^A-Z0-9]', '', 'g') = :brand"
            ),
            {"protocol": protocol, "ir_model": ir_model, "brand": brand},
        )


def downgrade():
    op.execute(
        "UPDATE air_conditioners SET ir_protocol=NULL, ir_model=1, ir_source='pending' "
        "WHERE ir_source='brand_candidate'"
    )
