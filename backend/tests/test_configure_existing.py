from argparse import Namespace

import pytest
from dotenv import dotenv_values
from sqlalchemy.engine import URL

from app import configure_existing
from app.configure_existing import connection_url


def options(**values) -> Namespace:
    defaults = {
        "url": None,
        "host": "127.0.0.1",
        "port": 5432,
        "user": "postgres",
        "database": "Movement",
    }
    return Namespace(**(defaults | values))


def test_supabase_url_receives_password_driver_and_tls():
    copied = (
        "postgresql://postgres.projeto:[YOUR-PASSWORD]"
        "@aws-1-us-west-2.pooler.supabase.com:5432/postgres"
    )
    url = connection_url(options(url=copied), "s3gredo:@/com-simbolos")
    assert url.drivername == "postgresql+psycopg"
    assert url.username == "postgres.projeto"
    assert url.password == "s3gredo:@/com-simbolos"
    assert url.host == "aws-1-us-west-2.pooler.supabase.com"
    assert url.database == "postgres"
    assert url.query["sslmode"] == "verify-full"
    assert url.query["sslrootcert"] == "system"


def test_local_database_keeps_default_tls_negotiation():
    url = connection_url(options(), "s3gredo")
    assert url.host == "127.0.0.1"
    assert "sslmode" not in url.query


@pytest.mark.parametrize("mode", ["verify-ca", "verify-full"])
def test_preserves_certificate_verification_and_explicit_ca(mode):
    url = connection_url(
        options(
            url=f"postgresql://sample@db.example.invalid/demo?sslmode={mode}&sslrootcert=ca.pem"
        ),
        "senha-sintetica",
    )
    assert url.query["sslmode"] == mode
    assert url.query["sslrootcert"] == "ca.pem"


@pytest.mark.parametrize(
    "query",
    ["host=db.example.invalid&sslmode=disable", "hostaddr=192.0.2.1", "password=override"],
)
def test_rejects_url_options_that_override_connection_parameters(query):
    with pytest.raises(ValueError):
        connection_url(
            options(url=f"postgresql://sample@localhost/demo?{query}"), "senha-sintetica"
        )


@pytest.mark.parametrize("filename", ["../credenciais.txt", ".env.example", "credenciais.txt"])
def test_rejects_unsafe_config_path_before_reading_password(monkeypatch, filename):
    def unexpected_prompt(_prompt):
        pytest.fail("A CLI pediu a senha antes de validar o destino")

    monkeypatch.setattr("sys.argv", ["configure_existing", "--env-file", filename])
    monkeypatch.setattr(configure_existing.getpass, "getpass", unexpected_prompt)
    with pytest.raises(SystemExit) as failure:
        configure_existing.main()
    assert failure.value.code == 2


def test_preserves_login_from_file_instead_of_process_environment(monkeypatch, tmp_path):
    destination = tmp_path / ".env.supabase"
    original = (
        "MOVEMENT_OPERATOR_USERNAME=admin_arquivo\n"
        f"MOVEMENT_SESSION_SECRET={'a' * 32}\n"
        "MOVEMENT_OPERATOR_PASSWORD_HASH=scrypt$hash_arquivo\n"
    )
    destination.write_text(original, encoding="utf-8")
    monkeypatch.setenv("MOVEMENT_OPERATOR_USERNAME", "admin_terminal")
    monkeypatch.setenv("MOVEMENT_SESSION_SECRET", "b" * 32)
    monkeypatch.setenv("MOVEMENT_OPERATOR_PASSWORD_HASH", "scrypt$hash_terminal")
    monkeypatch.setattr("sys.argv", ["configure_existing", "--env-file", destination.name])
    monkeypatch.setattr(configure_existing, "BACKEND", tmp_path)
    monkeypatch.setattr(configure_existing.getpass, "getpass", lambda _: "senha-sintetica")
    monkeypatch.setattr(configure_existing, "migrate_existing", lambda _url, publish: publish())
    configure_existing.main()
    values = dotenv_values(destination)
    assert values["MOVEMENT_OPERATOR_USERNAME"] == "admin_arquivo"
    assert values["MOVEMENT_SESSION_SECRET"] == "a" * 32
    assert values["MOVEMENT_OPERATOR_PASSWORD_HASH"] == "scrypt$hash_arquivo"
    assert next(tmp_path.glob(".env.backup-*")).read_text(encoding="utf-8") == original


def test_restores_existing_config_when_database_commit_fails(monkeypatch, tmp_path):
    destination = tmp_path / ".env"
    original = b"MOVEMENT_OPERATOR_USERNAME=admin_arquivo\n"
    destination.write_bytes(original)

    def reject_commit(_url, publish):
        publish()
        raise OSError("Falha simulada ao concluir a transação")

    monkeypatch.setattr(configure_existing, "BACKEND", tmp_path)
    monkeypatch.setattr(configure_existing, "migrate_existing", reject_commit)
    with pytest.raises(OSError, match="Falha simulada"):
        configure_existing.save_config(URL.create("postgresql"), destination, original, b"novo")
    assert destination.read_bytes() == original
    assert not list(tmp_path.glob(".env.stage-*"))
