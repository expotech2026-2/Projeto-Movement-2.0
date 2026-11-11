import json
import re
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from app.climate import ClimateUnavailable, Outside, Place, split_city
from app.dependencies import climate_service
from app.management import room_volume
from app.models import Room
from app.thermal import RoomThermal, room_thermal


class FakeClimate:
    def __init__(self):
        self.located = []

    def locate(self, city, uf=None):
        self.located.append((city, uf))
        if city == "Sem rede":
            raise ClimateUnavailable
        if city == "Cidade Inexistente":
            return None
        return Place("Campinas", "São Paulo", -22.9056, -47.0608)

    def outside(self, latitude, longitude):
        assert (latitude, longitude) == (-22.9056, -47.0608)
        return Outside(31.5, 48.0, "OpenWeatherMap")


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


SITE_BUTTONS = Path(__file__).parents[2] / "hardware" / "logica" / "controle_site.json"
REMAINING = re.compile(r'"remaining_seconds":(\d+)')


def test_site_buttons_reach_the_device_as_the_firmware_expects(context, climate):
    """Cada clique do site vira, para o ESP32, o texto que teste_controle.cpp dá ao firmware."""
    client = context["client"]
    for case in json.loads(SITE_BUTTONS.read_text(encoding="utf-8"))["casos"]:
        if case["comando"] is not None:
            sent = client.put(
                control_url(context), headers=context["professor_headers"], json=case["comando"]
            )
            assert sent.status_code == 200, case["botao"]
        text = client.get("/devices/me/control", headers=context["device_headers"]).text
        received = int(REMAINING.search(text).group(1))
        expected = int(REMAINING.search(case["resposta"]).group(1))
        assert abs(received - expected) <= 20, case["botao"]
        assert REMAINING.sub("", text) == REMAINING.sub("", case["resposta"]), case["botao"]


def test_room_computers_and_volume_reach_the_device(context, climate):
    """O ESP32 recebe capacidade, computadores e volume de ar para o alvo automático."""
    client, headers = context["client"], context["operator_headers"]
    path = f"/rooms/{context['room']}"
    room = {"name": "Laboratório", "unit_id": context["unit"], "capacity": 35, "computers": 30}
    for field, invalid in (
        ("computers", -1),
        ("computers", 10001),
        ("computers", "30"),
        ("area_m2", 0.5),
        ("ceiling_height_m", 1.5),
        ("ceiling_height_m", 25),
    ):
        response = client.put(path, headers=headers, json={**room, field: invalid})
        assert response.status_code == 422, (field, invalid)
    saved = client.put(path, headers=headers, json=room).json()
    assert (saved["capacity"], saved["computers"], saved["area_m2"]) == (35, 30, None)
    assert (saved["ceiling_height_m"], saved["volume_m3"]) == (3.0, 157.5)
    device = client.get("/devices/me/control", headers=context["device_headers"]).json()
    assert (device["capacity"], device["computers"]) == (35, 30)
    assert (device["ac_power_w"], device["ua_w_k"], device["fixed_heat_w"]) == (0.0, 125.0, 1910.7)
    appliance = {"name": "A/C", "kind": "split", "capacity_btu": 24000}
    for status in ("ativo", "manutencao"):
        sent = client.post(
            f"{path}/appliances", headers=headers, json={**appliance, "status": status}
        )
        assert sent.status_code == 201
    measured = {**room, "area_m2": 60.0, "ceiling_height_m": 3.0}
    assert client.put(path, headers=headers, json=measured).json()["volume_m3"] == 180.0
    device = client.get("/devices/me/control", headers=context["device_headers"]).json()
    assert (device["ac_power_w"], device["ua_w_k"], device["fixed_heat_w"]) == (
        5275.5,
        137.6,
        2081.4,
    )
    created = client.post(
        "/rooms", headers=headers, json={"name": "Sala comum", "unit_id": context["unit"]}
    ).json()
    assert (created["computers"], created["volume_m3"]) == (0, 20.0)


def test_room_volume_is_estimated_by_capacity_when_area_is_missing():
    assert [room_volume(None, 3.0, n) for n in (60, 70, 80)] == [270.0, 315.0, 360.0]
    assert room_volume(72.0, 3.0, 60) == 216.0
    assert room_volume(72.5, 2.8, 60) == 203.0
    assert room_volume(None, 3.0, 1) == 20.0


def test_room_thermal_follows_the_heat_load_table():
    """Sala de 60 m² com um ar de 24 000 BTU/h, como na Tabela 1 de tabela-carga-termica.md."""
    thermal = room_thermal(60.0, 3.0, 40, 24000)
    assert thermal == RoomThermal(ua_w_k=137.6, fixed_heat_w=2081.4, ac_power_w=5275.5)
    assert room_thermal(None, 3.0, 40, 0).ac_power_w == 0.0


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
        json={"name": f"Unidade Campinas {context['room']}", "city": "campinas - sp"},
    )
    assert unit.status_code == 200
    assert (unit.json()["city"], unit.json()["latitude"]) == ("Campinas - SP", -22.9056)
    assert climate.located == [("campinas", "SP")]

    renamed = client.put(
        f"/units/{context['unit']}",
        headers=headers,
        json={"name": f"Unidade Centro {context['room']}", "city": "Campinas - SP"},
    )
    assert renamed.status_code == 200
    assert climate.located == [("campinas", "SP")]

    device = client.get("/devices/me/control", headers=context["device_headers"]).json()
    assert (device["temp_outside"], device["humidity_outside"]) == (31.5, 48.0)
    state = client.get(control_url(context), headers=context["professor_headers"]).json()
    assert state["outside"] == {
        "city": "Campinas - SP",
        "temperature": 31.5,
        "humidity": 48.0,
        "source": "OpenWeatherMap",
    }


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Campinas - SP", ("Campinas", "SP")),
        ("bom jesus - pi", ("bom jesus", "PI")),
        ("Santa Bárbara d'Oeste - SP", ("Santa Bárbara d'Oeste", "SP")),
        ("Campinas", ("Campinas", None)),
        ("Campinas - XX", ("Campinas - XX", None)),
        (" - SP", ("- SP", None)),
    ],
)
def test_split_city_reads_the_state_at_the_end(text, expected):
    assert split_city(text) == expected


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
