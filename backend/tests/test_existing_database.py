from pathlib import Path
from uuid import uuid4

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text


def test_migrations_accept_an_existing_connection_without_committing_outer_transaction(
    database_url,
):
    engine = create_engine(database_url)
    with engine.connect() as connection:
        transaction = connection.begin()
        config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
        config.attributes["connection"] = connection
        command.downgrade(config, "0003_units_users_catalog")
        user_id = uuid4()
        connection.execute(
            text(
                "INSERT INTO users (id, username, full_name, role, password_hash, active) "
                "VALUES (:id, 'usuario-antigo', 'Usuário antigo', 'professor', 'teste', true)"
            ),
            {"id": user_id},
        )
        command.upgrade(config, "head")
        assert transaction.is_active
        assert connection.scalar(text("SELECT version_num FROM alembic_version")) == "0005_alerts"
        assert (
            connection.scalar(
                text("SELECT session_version FROM users WHERE id = :id"), {"id": user_id}
            )
            == 0
        )
        transaction.rollback()
    engine.dispose()
