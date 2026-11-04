from psycopg import sql
from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from app.settings import Settings


def build_engine(settings: Settings, **options) -> Engine:
    engine = create_engine(
        settings.database_url.get_secret_value(),
        pool_pre_ping=True,
        connect_args={"connect_timeout": 5},
        hide_parameters=True,
        **options,
    )
    schema = settings.database_schema
    if schema:
        # Poolers como o do Supabase ignoram o search_path da URL; cada conexão o define.
        @event.listens_for(engine, "connect", insert=True)
        def use_schema(dbapi_connection, _record):
            autocommit = dbapi_connection.autocommit
            dbapi_connection.autocommit = True
            with dbapi_connection.cursor() as cursor:
                cursor.execute(
                    sql.SQL("SET SESSION search_path TO {}").format(sql.Identifier(schema))
                )
            dbapi_connection.autocommit = autocommit

    return engine


def build_session_factory(settings: Settings) -> sessionmaker[Session]:
    return sessionmaker(build_engine(settings), expire_on_commit=False)
