from datetime import UTC, datetime, timedelta

import pytest

from app.climate import ClimateUnavailable, Outside, Place
from app.dependencies import climate_service
from app.models import Room


class FakeClimate:
    def __init__(self):
        self.located = []

    def locate(self, city):
        self.located.append(city)
        if city == "Sem rede":
            raise ClimateUnavailable
        if city == "Cidade Inexistente":
            return None
        return Place("Campinas", "São Paulo", -22.9056, -47.0608)

    def outside(self, latitude, longitude):
        assert (latitude, longitude) == (-22.9056, -47.0608)
        return Outside(31.5, 48.0)


@pytest.fixture
def climate(context):
    fake = FakeClimate()
    context["app"].dependency_overrides[climate_service] = lambda: fake
    yield fake
    context["app"].dependency_overrides.clear()


def control_url(context):
    return f"/rooms/{context['room']}/control"


def test_professor_sets_manual_temperature_and_device_receives_it(context, climate):
    client = context["client"]
    response = client.put(
        control_url(context),
        headers=context["professor_headers"],
        json={"mode": "manual", "target": 21},
    )
    assert response.status_code == 200
    body = response.json()
    assert (body["mode"], body["target"], body["version"]) == ("manual", 21, 1)
    assert body["changed_by"] == context["professor"]
    changed = datetime.fromisoformat(body["changed_at"])
    assert datetime.fromisoformat(body["expires_at"]) - changed == timedelta(hours=2)

    device = client.get("/devices/me/control", headers=context["device_headers"]).json()
    assert (device["version"], device["mode"], device["target"]) == (1, "manual", 21)
    assert 7190 <= device["remaining_seconds"] <= 7200
    assert device["temp_outside"] is None


def test_off_and_back_to_auto_increment_the_version(context, climate):
    client = context["client"]
    headers = context["operator_headers"]
    off = client.put(control_url(context), headers=headers, json={"mode": "off", "target": 22})
    assert off.status_code == 200
    assert (off.json()["mode"], off.json()["target"], off.json()["version"]) == ("off", None, 1)
    auto = client.put(control_url(context), headers=headers, json={"mode": "auto"}).json()
    assert (auto["mode"], auto["version"], auto["expires_at"]) == ("auto", 2, None)
    device = client.get("/devices/me/control", headers=context["device_headers"]).json()
    assert (device["mode"], device["remaining_seconds"]) == ("auto", 0)


@pytest.mark.parametrize(
    "payload",
    [
        {"mode": "manual"},
        {"mode": "manual", "target": 15},
        {"mode": "manual", "target": 31},
        {"mode": "manual", "target": "22"},
        {"mode": "turbo"},
        {"mode": "auto", "extra": 1},
    ],
)
def test_invalid_commands_are_rejected(context, climate, payload):
    response = context["client"].put(
        control_url(context), headers=context["professor_headers"], json=payload
    )
    assert response.status_code == 422


def test_manual_command_expires_after_two_hours(context, climate):
    client = context["client"]
    client.put(
        control_url(context),
        headers=context["professor_headers"],
        json={"mode": "manual", "target": 20},
    )
    with context["app"].state.sessions() as session:
        room = session.get(Room, context["room"])
        room.ac_changed_at = datetime.now(UTC) - timedelta(hours=2, seconds=1)
        session.commit()
    state = client.get(control_url(context), headers=context["professor_headers"]).json()
    assert (state["mode"], state["target"], state["expires_at"]) == ("auto", None, None)
    device = client.get("/devices/me/control", headers=context["device_headers"]).json()
    assert (device["version"], device["mode"], device["remaining_seconds"]) == (1, "auto", 0)


def test_control_requires_login_device_token_and_existing_room(context, climate):
    client = context["client"]
    assert client.get(control_url(context)).status_code == 401
    assert client.put(control_url(context), json={"mode": "off"}).status_code == 401
    assert client.get("/devices/me/control").status_code == 401
    assert (
        client.get("/devices/me/control", headers=context["professor_headers"]).status_code == 401
    )
    missing = client.put(
        "/rooms/nao-existe/control", headers=context["professor_headers"], json={"mode": "off"}
    )
    assert missing.status_code == 404


def test_unit_city_gives_the_device_the_outside_temperature(context, climate):
    client = context["client"]
    headers = context["operator_headers"]
    unit = client.put(
        f"/units/{context['unit']}",
        headers=headers,
        json={"name": f"Unidade Campinas {context['room']}", "city": "campinas"},
    )
    assert unit.status_code == 200
    assert (unit.json()["city"], unit.json()["latitude"]) == ("Campinas", -22.9056)
    assert climate.located == ["campinas"]

    renamed = client.put(
        f"/units/{context['unit']}",
        headers=headers,
        json={"name": f"Unidade Centro {context['room']}", "city": "Campinas"},
    )
    assert renamed.status_code == 200
    assert climate.located == ["campinas"]

    device = client.get("/devices/me/control", headers=context["device_headers"]).json()
    assert (device["temp_outside"], device["humidity_outside"]) == (31.5, 48.0)
    state = client.get(control_url(context), headers=context["professor_headers"]).json()
    assert state["outside"] == {
        "city": "Campinas",
        "temperature": 31.5,
        "humidity": 48.0,
        "source": "Open-Meteo",
    }


def test_unknown_city_or_offline_service_is_reported(context, climate):
    client = context["client"]
    headers = context["operator_headers"]
    name = f"Unidade sem cidade {context['room']}"
    unknown = {"name": name, "city": "Cidade Inexistente"}
    missing = client.post("/units", headers=headers, json=unknown)
    assert missing.status_code == 422
    assert missing.json()["detail"] == "Cidade não encontrada"
    offline = client.post("/units", headers=headers, json={"name": name, "city": "Sem rede"})
    assert offline.status_code == 503
    plain = client.post("/units", headers=headers, json={"name": name}).json()
    assert (plain["city"], plain["latitude"], plain["longitude"]) == ("", None, None)
