from pathlib import Path

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
        command.upgrade(config, "head")
        assert transaction.is_active
        assert (
            connection.scalar(text("SELECT version_num FROM alembic_version"))
            == "0003_units_users_catalog"
        )
        transaction.rollback()
    engine.dispose()
