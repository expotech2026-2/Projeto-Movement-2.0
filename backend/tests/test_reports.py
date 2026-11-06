from datetime import UTC, datetime
from uuid import uuid4

from app.reports import collect


def test_pdf_report_covers_scopes_and_is_available_to_professors(context):
    client, admin, teacher = (
        context["client"],
        context["operator_headers"],
        context["professor_headers"],
    )
    model = client.get(
        "/catalog/models", headers=admin, params={"brand": "LG", "kind": "split", "limit": 1}
    ).json()[0]
    appliance = {
        "name": "A/C fundos",
        "kind": "split",
        "brand": model["brand"],
        "model": model["model"],
        "capacity_btu": model["capacity_btu"],
        "inverter": model["inverter"],
    }
    room = context["room"]
    assert (
        client.post(f"/rooms/{room}/appliances", headers=admin, json=appliance).status_code == 201
    )
    reading = {
        "message_id": str(uuid4()),
        "measured_at": datetime.now(UTC).isoformat(),
        "occupancy": 12,
        "temp_inside": 23.5,
        "temp_outside": 31.0,
        "target_temp": 23.0,
        "humidity_inside": 52.0,
        "humidity_outside": 70.0,
        "ac_on": True,
        "manual_mode": False,
    }
    assert (
        client.post("/telemetry", headers=context["device_headers"], json=reading).status_code
        == 201
    )
    for headers, params in (
        (admin, {}),
        (teacher, {"unit_id": context["unit"]}),
        (teacher, {"room_id": room}),
    ):
        response = client.get("/reports/pdf", headers=headers, params=params)
        assert response.status_code == 200, params
        assert response.headers["content-type"] == "application/pdf"
        assert response.headers["content-disposition"].startswith("attachment;")
        assert response.content.startswith(b"%PDF") and len(response.content) > 3000
    assert client.get("/reports/pdf").status_code == 401
    assert client.get("/reports/pdf", headers=admin, params={"room_id": "x"}).status_code == 404
    assert client.get("/reports/pdf", headers=admin, params={"unit_id": "x"}).status_code == 404
    with context["app"].state.sessions() as session:
        groups, scope = collect(session, context["unit"], None)
    assert scope.startswith("Unidade ")
    ((unit, reports),) = groups
    assert unit.id == context["unit"]
    (report,) = [item for item in reports if item.room.id == room]
    assert report.latest is not None and report.has_device
    (item,) = report.appliances
    assert report.energy[item.id].registration == model["registration"]
