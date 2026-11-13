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
        password = "senha-sintetica-" * 20
        invalid = client.post("/api/auth/login", json={"username": "admin", "password": password})
        assert invalid.status_code == 422
        assert password not in invalid.text
        assert client.get("/api/openapi.json").status_code == 200
        assert client.get("/health").status_code == 404


def test_site_compresses_answers_and_lets_the_browser_keep_hashed_files(database_url, tmp_path):
    (tmp_path / "index.html").write_text('<div id="root"></div>', encoding="utf-8")
    (tmp_path / "assets").mkdir()
    (tmp_path / "assets" / "index-abc123.js").write_bytes(b"// movement\n" * 500)
    settings = Settings(
        database_url=database_url,
        session_secret=secrets.token_urlsafe(32),
        operator_password_hash=hash_password("test-password-123"),
        retention_enabled=False,
    )
    with TestClient(create_site(settings, frontend=tmp_path)) as client:
        assert client.get("/").headers["cache-control"] == "no-cache"
        script = client.get("/assets/index-abc123.js")
        assert script.headers["cache-control"] == "public, max-age=31536000, immutable"
        assert script.headers["content-encoding"] == "gzip"
        assert script.text == "// movement\n" * 500
        api = client.get("/api/openapi.json")
        assert api.headers["content-encoding"] == "gzip"
        assert api.headers["cache-control"] == "no-store"
        plain = client.get("/assets/index-abc123.js", headers={"Accept-Encoding": "identity"})
        assert "content-encoding" not in plain.headers
