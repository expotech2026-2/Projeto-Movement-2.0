import argparse
import getpass
import os
import re
import secrets
import subprocess
from collections.abc import Callable
from io import StringIO
from pathlib import Path
from tempfile import mkstemp

from alembic import command
from alembic.config import Config
from dotenv import dotenv_values
from pydantic import SecretStr
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL, make_url
from sqlalchemy.exc import SQLAlchemyError

from app.security import hash_password
from app.settings import Settings

BACKEND = Path(__file__).resolve().parents[1]
LOCAL_HOSTS = {"127.0.0.1", "localhost", "::1"}
TLS_OPTIONS = {"sslmode", "sslrootcert"}


def connection_url(args: argparse.Namespace, password: str) -> URL:
    if args.url:
        url = make_url(args.url).set(drivername="postgresql+psycopg", password=password)
    else:
        url = URL.create(
            "postgresql+psycopg",
            username=args.user,
            password=password,
            host=args.host,
            port=args.port,
            database=args.database,
        )
    if not url.host or any(char in url.host for char in ",/\\"):
        raise ValueError("Informe um único host PostgreSQL")
    if url.query.keys() - TLS_OPTIONS or any(
        not isinstance(value, str) for value in url.query.values()
    ):
        raise ValueError("A URL aceita apenas uma ocorrência de sslmode e sslrootcert")
    if os.environ.get("PGHOSTADDR") or os.environ.get("PGSERVICE"):
        raise ValueError("Remova PGHOSTADDR e PGSERVICE do terminal antes de configurar o banco")
    if url.host.lower() not in LOCAL_HOSTS:
        mode = url.query.get("sslmode")
        if mode not in {"verify-ca", "verify-full"}:
            mode = "verify-full"
        url = url.update_query_dict({"sslmode": mode, "gssencmode": "disable"})
        if mode == "verify-full" and not url.query.get("sslrootcert"):
            url = url.update_query_dict({"sslrootcert": "system"})
    return url


def migrate_existing(url: URL, publish: Callable[[], None]) -> None:
    engine = create_engine(url, hide_parameters=True, connect_args={"connect_timeout": 5})
    try:
        with engine.begin() as connection:
            existing = (
                connection.execute(
                    text("""
                SELECT tablename FROM pg_tables WHERE schemaname = 'movement'
            """)
                )
                .scalars()
                .all()
            )
            if existing and "alembic_version" not in existing:
                raise ValueError(
                    "Schema movement contém tabelas sem controle Alembic; configuração preservada"
                )
            connection.execute(text("CREATE SCHEMA IF NOT EXISTS movement"))
            connection.execute(text("SET LOCAL search_path TO movement"))
            config = Config(str(BACKEND / "alembic.ini"))
            config.attributes["connection"] = connection
            command.upgrade(config, "head")
            publish()
    finally:
        engine.dispose()


def private_file(contents: bytes, prefix: str) -> Path:
    descriptor, filename = mkstemp(dir=BACKEND, prefix=prefix)
    path = Path(filename)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            if os.name == "nt":
                system = Path(os.environ["SystemRoot"]) / "System32"
                identity = subprocess.check_output(
                    [str(system / "whoami.exe"), "/user", "/fo", "csv", "/nh"],
                    creationflags=subprocess.CREATE_NO_WINDOW,
                )
                sid = re.search(rb"S-1-(?:\d+-)+\d+", identity)
                if sid is None:
                    raise OSError("Não foi possível identificar o usuário do Windows")
                subprocess.run(
                    [
                        str(system / "icacls.exe"),
                        filename,
                        "/inheritance:r",
                        "/grant:r",
                        f"*{sid.group().decode('ascii')}:(F)",
                    ],
                    check=True,
                    capture_output=True,
                    creationflags=subprocess.CREATE_NO_WINDOW,
                )
            stream.write(contents)
            stream.flush()
            os.fsync(stream.fileno())
    except BaseException:
        path.unlink(missing_ok=True)
        raise
    return path


def read_config(path: Path) -> bytes | None:
    if path.is_symlink() or (path.exists() and not path.is_file()):
        raise ValueError("O arquivo de configuração deve ser um arquivo regular em backend/")
    return path.read_bytes() if path.exists() else None


def save_config(url: URL, path: Path, previous: bytes | None, contents: bytes) -> None:
    staged = private_file(contents, ".env.stage-")
    backup = None
    published = False

    def publish() -> None:
        nonlocal published
        if read_config(path) != previous:
            raise ValueError("O arquivo mudou durante a configuração")
        staged.replace(path)
        published = True

    try:
        if previous is not None:
            backup = private_file(previous, ".env.backup-")
        migrate_existing(url, publish)
    except BaseException:
        if published and read_config(path) == contents:
            if backup is None:
                path.unlink()
            else:
                backup.replace(path)
        elif not published and backup is not None:
            backup.unlink()
        raise
    finally:
        staged.unlink(missing_ok=True)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Conectar ao banco existente Movement sem alterar tabelas de outros schemas"
    )
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=5432)
    parser.add_argument("--user", default="postgres")
    parser.add_argument("--database", default="Movement")
    parser.add_argument("--url", help="URL sem senha, como a do Session pooler do Supabase")
    parser.add_argument("--env-file", default=".env", help="Arquivo de configuração em backend/")
    args = parser.parse_args()
    if not re.fullmatch(r"\.env(?:\.[A-Za-z0-9_-]+)*", args.env_file) or (
        args.env_file.lower() == ".env.example"
    ):
        parser.error("Informe .env ou .env.<nome> em backend/, por exemplo .env.supabase")
    dotenv = BACKEND / args.env_file
    try:
        previous = read_config(dotenv)
    except (OSError, ValueError):
        parser.exit(1, "Não foi possível ler o arquivo de configuração em backend/.\n")
    password = getpass.getpass("Senha PostgreSQL (não será exibida): ")
    try:
        url = connection_url(args, password)
    except (SQLAlchemyError, ValueError):
        parser.exit(1, "URL PostgreSQL inválida ou com parâmetros de conexão não permitidos.\n")
    if previous is not None:
        try:
            stored = dotenv_values(stream=StringIO(previous.decode("utf-8")), interpolate=False)
            session_secret = Settings.strong_secret(
                SecretStr(stored.get("MOVEMENT_SESSION_SECRET") or "")
            ).get_secret_value()
            password_hash = Settings.password_hash_format(
                SecretStr(stored.get("MOVEMENT_OPERATOR_PASSWORD_HASH") or "")
            ).get_secret_value()
            username = stored.get("MOVEMENT_OPERATOR_USERNAME") or "admin"
            if any("${" in value for value in (session_secret, password_hash, username)):
                raise ValueError("Credenciais devem ter valores literais")
        except ValueError:
            parser.exit(
                1, "As credenciais do arquivo de configuração estão incompletas ou inválidas.\n"
            )
    else:
        operator_password = getpass.getpass("Crie a senha do operador (mínimo 12 caracteres): ")
        if len(operator_password) < 12 or operator_password != getpass.getpass(
            "Confirme a senha do operador: "
        ):
            parser.exit(1, "Senha curta ou confirmação diferente; nenhuma alteração realizada.\n")
        password_hash = hash_password(operator_password)
        session_secret = secrets.token_urlsafe(48)
        username = "admin"
    values = {
        "MOVEMENT_DATABASE_URL": url.render_as_string(hide_password=False),
        "MOVEMENT_DATABASE_SCHEMA": "movement",
        "MOVEMENT_SESSION_SECRET": session_secret,
        "MOVEMENT_OPERATOR_USERNAME": username,
        "MOVEMENT_OPERATOR_PASSWORD_HASH": password_hash,
        "MOVEMENT_CORS_ORIGINS": '["http://localhost:5173","http://127.0.0.1:5173"]',
        "MOVEMENT_RETENTION_ENABLED": "true",
        "MOVEMENT_RETENTION_INTERVAL_SECONDS": "3600",
    }
    lines = []
    for key, value in values.items():
        escaped = value.replace("\\", "\\\\").replace("'", "\\'")
        lines.append(f"{key}='{escaped}'\n")
    try:
        save_config(url, dotenv, previous, "".join(lines).encode("utf-8"))
    except (SQLAlchemyError, ValueError, OSError, subprocess.SubprocessError):
        parser.exit(1, "Falha ao preparar o arquivo, conectar ao banco ou aplicar as migrações.\n")
    print(
        "Banco conectado e migrações aplicadas. No pgAdmin: Movement > Schemas > movement > Tables."
    )
    print(f"Configuração gravada em backend/{args.env_file}.")
    login = (
        "O login configurado foi mantido." if previous is not None else "O login admin foi criado."
    )
    print(
        f"Reinicie a API. {login} "
        "Uma configuração anterior, se existente, foi copiada para um backup privado."
    )


if __name__ == "__main__":
    main()
