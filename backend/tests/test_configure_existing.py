from argparse import Namespace

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
    assert url.query["sslmode"] == "require"


def test_local_database_keeps_default_tls_negotiation():
    url = connection_url(options(), "s3gredo")
    assert url.host == "127.0.0.1"
    assert "sslmode" not in url.query
