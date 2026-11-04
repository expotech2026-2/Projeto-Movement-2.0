import secrets

from fastapi.testclient import TestClient

from app.security import hash_password
from app.settings import Settings
from app.site import create_site


def test_site_serves_frontend_at_root_and_api_under_prefix(database_url, tmp_path):
    (tmp_path / "index.html").write_text('<div id="root"></div>', encoding="utf-8")
    settings = Settings(
        database_url=database_url,
        session_secret=secrets.token_urlsafe(32),
        operator_password_hash=hash_password("test-password-123"),
        retention_enabled=False,
    )
    with TestClient(create_site(settings, frontend=tmp_path)) as client:
        page = client.get("/")
        assert page.status_code == 200
        assert '<div id="root">' in page.text
        assert client.get("/api/ready").json() == {"status": "ready"}
        login = client.post(
            "/api/auth/login", json={"username": "admin", "password": "test-password-123"}
        )
        assert login.status_code == 200
        assert client.get("/api/openapi.json").status_code == 200
        assert client.get("/health").status_code == 404
