import argparse
import getpass
import secrets
from datetime import UTC, datetime
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL, make_url
from sqlalchemy.exc import SQLAlchemyError

from app.security import hash_password
from app.settings import Settings

BACKEND = Path(__file__).resolve().parents[1]
LOCAL_HOSTS = {"127.0.0.1", "localhost", "::1"}


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
    # Bancos fora desta máquina, como o Supabase, recebem a conexão sempre cifrada.
    if url.host not in LOCAL_HOSTS:
        url = url.update_query_dict({"sslmode": "require"})
    return url


def migrate_existing(url: URL):
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
    finally:
        engine.dispose()


def main():
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
    password = getpass.getpass("Senha PostgreSQL (não será exibida): ")
    url = connection_url(args, password)
    dotenv = BACKEND / args.env_file
    kept_login = dotenv.exists()
    if kept_login:
        settings = Settings(_env_file=dotenv)
        session_secret = settings.session_secret.get_secret_value()
        password_hash = settings.operator_password_hash.get_secret_value()
        username = settings.operator_username
    else:
        operator_password = getpass.getpass("Crie a senha do operador (mínimo 12 caracteres): ")
        if len(operator_password) < 12 or operator_password != getpass.getpass(
            "Confirme a senha do operador: "
        ):
            parser.exit(1, "Senha curta ou confirmação diferente; nenhuma alteração realizada.\n")
        password_hash = hash_password(operator_password)
        session_secret = secrets.token_urlsafe(48)
        username = "admin"
    try:
        migrate_existing(url)
    except (SQLAlchemyError, ValueError) as error:
        detail = (
            str(error)
            if isinstance(error, ValueError)
            else "Falha de conexão ou migração; confira banco, host, porta, usuário e senha"
        )
        parser.exit(1, detail + "; arquivo .env preservado.\n")
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
    if dotenv.exists():
        backup = dotenv.with_name(f".env.backup-{datetime.now(UTC):%Y%m%d%H%M%S%f}")
        backup.write_bytes(dotenv.read_bytes())
    dotenv.write_text(
        "\n".join(f"{key}={value}" for key, value in values.items()) + "\n", encoding="utf-8"
    )
    print(
        "Banco conectado e migrações aplicadas. No pgAdmin: Movement > Schemas > movement > Tables."
    )
    print(f"Configuração gravada em backend/{args.env_file}.")
    login = "O login configurado foi mantido." if kept_login else "O login admin foi criado."
    print(
        f"Reinicie a API. {login} "
        "Uma configuração anterior, se existente, foi copiada para um backup privado."
    )


if __name__ == "__main__":
    main()
