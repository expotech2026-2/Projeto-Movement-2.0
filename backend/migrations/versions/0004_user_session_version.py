"""Revoga sessões de usuários quando o acesso ou o perfil muda."""

import sqlalchemy as sa
from alembic import op

revision = "0004_user_session_version"
down_revision = "0003_units_users_catalog"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users", sa.Column("session_version", sa.Integer(), server_default="0", nullable=False)
    )


def downgrade() -> None:
    op.drop_column("users", "session_version")
