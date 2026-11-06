from uuid import uuid4


def login(client, username, password):
    return client.post("/auth/login", json={"username": username, "password": password})


def bearer(response):
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_professor_reads_everything_but_cannot_change_anything(context):
    client, teacher = context["client"], context["professor_headers"]
    room, unit = context["room"], context["unit"]
    me = client.get("/auth/me", headers=teacher).json()
    assert me["role"] == "professor" and me["builtin"] is False
    for path in (
        "/units",
        "/rooms",
        f"/rooms/{room}/appliances",
        f"/rooms/{room}/devices",
        f"/rooms/{room}/latest",
        f"/rooms/{room}/monthly",
        "/catalog/brands",
    ):
        assert client.get(path, headers=teacher).status_code == 200, path
    forbidden = [
        ("post", "/units", {"name": "Proibida"}),
        ("put", f"/units/{unit}", {"name": "Proibida"}),
        ("delete", f"/units/{unit}", None),
        ("post", "/rooms", {"name": "Proibida", "unit_id": unit}),
        ("put", f"/rooms/{room}", {"name": "Proibida", "unit_id": unit}),
        ("delete", f"/rooms/{room}", None),
        ("post", f"/rooms/{room}/appliances", {"name": "A", "kind": "split", "capacity_btu": 9000}),
        ("post", f"/rooms/{room}/devices", None),
        ("get", "/users", None),
        ("post", "/users", {}),
    ]
    for method, path, body in forbidden:
        kwargs = {"headers": teacher} | ({"json": body} if body is not None else {})
        assert getattr(client, method)(path, **kwargs).status_code == 403, (method, path)


def test_admin_manages_users_and_sessions_follow_account_changes(context):
    client, admin = context["client"], context["operator_headers"]
    username = f"ana.{uuid4().hex[:8]}"
    created = client.post(
        "/users",
        headers=admin,
        json={
            "username": f"  {username.upper()} ",
            "full_name": "Ana Souza",
            "role": "professor",
            "password": "senha-forte-123",
        },
    )
    assert created.status_code == 201
    user = created.json()
    assert user["username"] == username and "password_hash" not in user
    duplicate = {
        "username": username,
        "full_name": "Outra",
        "role": "professor",
        "password": "senha-forte-123",
    }
    assert client.post("/users", headers=admin, json=duplicate).status_code == 409
    reserved = {**duplicate, "username": "admin"}
    assert client.post("/users", headers=admin, json=reserved).status_code == 409
    short = {**duplicate, "username": f"x{uuid4().hex[:8]}", "password": "curta"}
    assert client.post("/users", headers=admin, json=short).status_code == 422
    assert login(client, username, "senha-errada-123").status_code == 401
    first = login(client, username, "senha-forte-123")
    assert first.status_code == 200
    assert first.json()["user"] == {
        "username": username,
        "full_name": "Ana Souza",
        "role": "professor",
        "builtin": False,
    }
    path = f"/users/{user['id']}"
    changed = {"full_name": "Ana Souza", "role": "professor", "password": "nova-senha-456"}
    assert client.put(path, headers=admin, json=changed).status_code == 200
    assert client.get("/auth/me", headers=bearer(first)).status_code == 401
    second = login(client, username, "nova-senha-456")
    assert client.get("/auth/me", headers=bearer(second)).status_code == 200
    inactive = {"full_name": "Ana Souza", "role": "professor", "active": False}
    assert client.put(path, headers=admin, json=inactive).json()["active"] is False
    assert client.get("/auth/me", headers=bearer(second)).status_code == 401
    assert login(client, username, "nova-senha-456").status_code == 401
    reactivated = {**inactive, "active": True}
    assert client.put(path, headers=admin, json=reactivated).status_code == 200
    assert client.get("/auth/me", headers=bearer(second)).status_code == 401
    third = bearer(login(client, username, "nova-senha-456"))
    assert client.get("/auth/me", headers=third).status_code == 200
    promoted = {"full_name": "Ana Souza", "role": "admin", "active": True}
    assert client.put(path, headers=admin, json=promoted).json()["role"] == "admin"
    assert client.get("/users", headers=third).status_code == 401
    own = bearer(login(client, username, "nova-senha-456"))
    assert client.get("/users", headers=own).status_code == 200
    demote_self = {"full_name": "Ana Souza", "role": "professor", "active": True}
    assert client.put(path, headers=own, json=demote_self).status_code == 409
    assert client.delete(path, headers=own).status_code == 409
    assert client.delete(path, headers=admin).status_code == 204
    assert client.get("/auth/me", headers=own).status_code == 401
    assert client.delete(path, headers=admin).status_code == 404


def test_validation_errors_do_not_echo_passwords(context):
    client, admin = context["client"], context["operator_headers"]
    password = "senha-sintetica-" * 20
    user = {"full_name": "Ana Souza", "role": "professor", "password": password}
    invalid_responses = (
        login(client, "admin", password),
        client.post("/users", headers=admin, json={**user, "username": "ana.souza"}),
        client.put(f"/users/{uuid4()}", headers=admin, json=user),
        client.post("/users", headers=admin, json=[user]),
    )
    for response in invalid_responses:
        assert response.status_code == 422
        assert password not in response.text
        assert all(set(detail) == {"loc", "msg", "type"} for detail in response.json()["detail"])
