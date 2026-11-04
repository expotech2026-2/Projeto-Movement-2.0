import secrets

from sqlalchemy import text
from sqlalchemy.engine import make_url

from app.database import build_engine
from app.security import hash_password
from app.settings import Settings


def test_engine_selects_configured_schema_on_every_connection(database_url):
    url = make_url(database_url)
    schema = url.query["options"].removeprefix("-csearch_path=")
    settings = Settings(
        database_url=url.difference_update_query(["options"]).render_as_string(hide_password=False),
        database_schema=schema,
        session_secret=secrets.token_urlsafe(32),
        operator_password_hash=hash_password("test-password-123"),
    )
    engine = build_engine(settings, pool_size=1, max_overflow=0)
    try:
        for _ in range(2):
            with engine.connect() as connection:
                assert connection.scalar(text("SELECT current_schema()")) == schema
                assert connection.scalar(text("SELECT count(*) FROM alembic_version")) == 1
    finally:
        engine.dispose()
