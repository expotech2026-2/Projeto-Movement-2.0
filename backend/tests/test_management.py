from datetime import UTC, datetime, timedelta
from uuid import uuid4


def test_room_and_appliance_crud_are_authenticated_and_scoped(context):
    client, headers, unit = context["client"], context["operator_headers"], context["unit"]
    assert client.get("/rooms").status_code == 401
    assert client.post("/rooms", json={"name": "Teste", "unit_id": unit}).status_code == 401
    assert client.post("/rooms", headers=headers, json={"name": "Sem unidade"}).status_code == 422
    assert (
        client.post(
            "/rooms", headers=headers, json={"name": "Órfã", "unit_id": "inexistente"}
        ).status_code
        == 422
    )
    room = client.post(
        "/rooms",
        headers=headers,
        json={"name": "Laboratório", "unit_id": unit, "location": "Bloco A", "capacity": 35},
    ).json()
    other = client.post(
        "/rooms", headers=headers, json={"name": "Biblioteca", "unit_id": unit}
    ).json()
    path = f"/rooms/{room['id']}"
    payload = {"name": "A/C 01", "kind": "split", "capacity_btu": 18000, "inverter": True}
    response = client.post(f"{path}/appliances", headers=headers, json=payload)
    assert response.status_code == 201
    appliance = response.json()
    second = client.post(f"{path}/appliances", headers=headers, json={**payload, "kind": "cassete"})
    assert second.status_code == 201
    assert len(client.get(f"{path}/appliances", headers=headers).json()) == 2
    assert client.get(f"/rooms/{other['id']}/appliances", headers=headers).json() == []
    counts = {
        item["id"]: item["appliance_count"]
        for item in client.get("/rooms", headers=headers, params={"unit_id": unit}).json()
    }
    assert (counts[room["id"]], counts[other["id"]]) == (2, 0)
    assert room["appliance_count"] == 0
    assert (
        client.put(
            f"/rooms/{other['id']}/appliances/{appliance['id']}", headers=headers, json=payload
        ).status_code
        == 404
    )
    assert (
        client.put(
            f"{path}/appliances/{appliance['id']}",
            headers=headers,
            json={**payload, "status": "manutencao"},
        ).json()["status"]
        == "manutencao"
    )
    assert (
        client.post(
            f"{path}/appliances", headers=headers, json={**payload, "kind": "invalid"}
        ).status_code
        == 422
    )
    assert (
        client.put(
            path, headers=headers, json={"name": "Laboratório 2", "unit_id": unit, "capacity": 40}
        ).json()["capacity"]
        == 40
    )
    assert client.delete(path, headers=headers).status_code == 409
    for item in (appliance, second.json()):
        assert client.delete(f"{path}/appliances/{item['id']}", headers=headers).status_code == 204
    assert client.delete(path, headers=headers).status_code == 204
    assert client.get(f"{path}/monthly", headers=headers).status_code == 404


def test_units_group_rooms_and_are_only_removed_when_empty(context):
    client, headers = context["client"], context["operator_headers"]
    suffix = uuid4().hex[:8]
    centro = client.post(
        "/units", headers=headers, json={"name": f"Centro {suffix}", "address": "Rua A, 10"}
    )
    assert centro.status_code == 201
    sede = client.post("/units", headers=headers, json={"name": f"Polo Sede {suffix}"}).json()
    centro = centro.json()
    assert client.post("/units", headers=headers, json={"name": centro["name"]}).status_code == 409
    for name in ("Sala 101", "Sala 102"):
        created = client.post(
            "/rooms", headers=headers, json={"name": name, "unit_id": centro["id"]}
        )
        assert created.status_code == 201
    moving = client.post(
        "/rooms", headers=headers, json={"name": "Auditório", "unit_id": centro["id"]}
    ).json()
    units = {item["id"]: item for item in client.get("/units", headers=headers).json()}
    assert units[centro["id"]]["room_count"] == 3
    assert units[sede["id"]]["room_count"] == 0
    listed = client.get("/rooms", headers=headers, params={"unit_id": centro["id"]}).json()
    assert {item["name"] for item in listed} == {"Sala 101", "Sala 102", "Auditório"}
    moved = client.put(
        f"/rooms/{moving['id']}",
        headers=headers,
        json={"name": "Auditório", "unit_id": sede["id"], "capacity": 120},
    )
    assert moved.json()["unit_id"] == sede["id"]
    assert client.delete(f"/units/{sede['id']}", headers=headers).status_code == 409
    assert client.delete(f"/rooms/{moving['id']}", headers=headers).status_code == 204
    renamed = client.put(f"/units/{sede['id']}", headers=headers, json={"name": f"Sede {suffix}"})
    assert renamed.json()["name"] == f"Sede {suffix}"
    assert client.delete(f"/units/{sede['id']}", headers=headers).status_code == 204
    assert client.get(f"/units/{sede['id']}", headers=headers).status_code in (404, 405)


def test_device_credential_is_unique_and_telemetry_is_bound_to_room(context):
    client, headers = context["client"], context["operator_headers"]
    room = client.post(
        "/rooms", headers=headers, json={"name": "Sala nova", "unit_id": context["unit"]}
    ).json()
    path = f"/rooms/{room['id']}"
    response = client.post(f"{path}/devices", headers=headers)
    assert response.status_code == 201
    credential = response.json()
    assert len(credential["token"]) >= 32
    assert "token" not in client.get(f"{path}/devices", headers=headers).json()[0]
    assert client.post(f"{path}/devices", headers=headers).status_code == 409
    payload = {
        "message_id": str(uuid4()),
        "measured_at": datetime.now(UTC).isoformat(),
        "occupancy": 2,
        "temp_inside": 24,
        "temp_outside": 28,
        "humidity_inside": 50,
        "humidity_outside": 60,
        "target_temp": 23,
        "ac_on": True,
        "manual_mode": False,
    }
    device_headers = {"Authorization": f"Bearer {credential['token']}"}
    reading = client.post("/telemetry", headers=device_headers, json=payload)
    assert reading.status_code == 201
    assert reading.json()["reading"]["room_id"] == room["id"]
    assert client.get(f"/rooms/{context['room']}/latest", headers=headers).json()["reading"] is None
    payload["message_id"] = str(uuid4())
    payload["measured_at"] = (datetime.now(UTC) - timedelta(days=31)).isoformat()
    assert client.post("/telemetry", headers=device_headers, json=payload).status_code == 422
