import hashlib
import secrets
import ssl

import pytest
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.pool import NullPool

from app.database import BACKEND, SUPABASE_CA, build_engine, with_local_ca
from app.security import hash_password
from app.settings import Settings

SUPABASE_ROOT_SHA256 = "807025ad50d4ed219d2c9c7d299c004f824eb00cf7f65afef607d07b72e6cafa"


def test_bundled_ca_is_the_supabase_root_2021():
    pem = (BACKEND / SUPABASE_CA).read_text(encoding="ascii")
    assert hashlib.sha256(ssl.PEM_cert_to_DER_cert(pem)).hexdigest() == SUPABASE_ROOT_SHA256


def test_relative_ca_is_found_from_any_working_directory(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    url = make_url(f"postgresql+psycopg://u@db.example.invalid/d?sslrootcert={SUPABASE_CA}")
    resolved = tmp_path / with_local_ca(url).query["sslrootcert"]
    assert resolved.resolve() == (BACKEND / SUPABASE_CA).resolve()


@pytest.mark.parametrize("root", ["system", str(BACKEND / SUPABASE_CA), None])
def test_system_absolute_and_missing_ca_are_kept(root):
    url = make_url("postgresql+psycopg://u@db.example.invalid/d")
    if root:
        url = url.update_query_dict({"sslrootcert": root})
    assert with_local_ca(url) == url


def test_engine_selects_configured_schema_on_every_connection(database_url):
    url = make_url(database_url)
    schema = url.query["options"].removeprefix("-csearch_path=")
    settings = Settings(
        database_url=url.difference_update_query(["options"]).render_as_string(hide_password=False),
        database_schema=schema,
        session_secret=secrets.token_urlsafe(32),
        operator_password_hash=hash_password("test-password-123"),
    )
    engine = build_engine(settings, poolclass=NullPool)
    try:
        connection_ids = set()
        for _ in range(2):
            with engine.connect() as connection:
                connection_ids.add(connection.scalar(text("SELECT pg_backend_pid()")))
                assert connection.scalar(text("SELECT current_schema()")) == schema
                assert connection.scalar(text("SELECT count(*) FROM alembic_version")) == 1
        assert len(connection_ids) == 2
    finally:
        engine.dispose()
