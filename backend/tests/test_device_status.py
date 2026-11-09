from datetime import UTC, datetime, timedelta

from starlette.requests import Request

from app.device_status import OFFLINE_AFTER, diagnostics, is_online, record_contact
from app.models import Device

NOW = datetime(2026, 11, 9, 14, 0, tzinfo=UTC)
DIAGNOSTIC_HEADERS = {
    "X-Movement-Firmware": "2.1.0",
    "X-Movement-RSSI": "-67",
    "X-Movement-Uptime": "3600",
    "X-Movement-Sensors": "ok",
    "X-Movement-AC": "ligado 22 C, GREE",
}


def request_with(headers: dict[str, str]) -> Request:
    raw = [(key.lower().encode(), value.encode()) for key, value in headers.items()]
    return Request({"type": "http", "headers": raw})


def test_diagnostics_keep_only_valid_headers():
    assert diagnostics(request_with(DIAGNOSTIC_HEADERS)) == {
        "firmware": "2.1.0",
        "rssi": -67,
        "uptime_seconds": 3600,
        "sensor_faults": "ok",
        "ac_state": "ligado 22 C, GREE",
    }
    broken = {"X-Movement-RSSI": "forte", "X-Movement-Uptime": "-5", "X-Movement-AC": "x" * 90}
    assert diagnostics(request_with(broken)) == {"ac_state": "x" * 60}
    assert diagnostics(request_with({})) == {}


def test_contact_is_written_when_new_or_every_ten_seconds():
    device = Device(id="esp32-teste", room_id="sala", token_hash="h")
    assert record_contact(device, request_with(DIAGNOSTIC_HEADERS), NOW)
    assert (device.last_seen_at, device.rssi, device.firmware) == (NOW, -67, "2.1.0")

    soon = NOW + timedelta(seconds=5)
    assert not record_contact(device, request_with(DIAGNOSTIC_HEADERS), soon)
    assert device.last_seen_at == NOW
    weaker = {**DIAGNOSTIC_HEADERS, "X-Movement-RSSI": "-85"}
    assert record_contact(device, request_with(weaker), soon)
    assert (device.last_seen_at, device.rssi) == (soon, -85)
    assert record_contact(device, request_with({}), soon + timedelta(seconds=10))
    assert device.firmware == "2.1.0"


def test_online_until_150_seconds_without_contact():
    assert is_online(NOW, NOW + OFFLINE_AFTER - timedelta(seconds=1))
    assert not is_online(NOW, NOW + OFFLINE_AFTER)
    assert not is_online(None, NOW)


def test_site_sees_the_device_online_with_its_diagnostics(context):
    client = context["client"]
    devices_url = f"/rooms/{context['room']}/devices"
    before = client.get(devices_url, headers=context["professor_headers"]).json()
    assert (before[0]["online"], before[0]["last_seen_at"], before[0]["rssi"]) == (
        False,
        None,
        None,
    )

    headers = {**context["device_headers"], **DIAGNOSTIC_HEADERS}
    assert client.get("/devices/me/control", headers=headers).status_code == 200
    device = client.get(devices_url, headers=context["professor_headers"]).json()[0]
    assert device["online"] is True
    assert device["seconds_since_contact"] <= 5
    assert (device["firmware"], device["rssi"], device["uptime_seconds"]) == ("2.1.0", -67, 3600)
    assert (device["sensor_faults"], device["ac_state"]) == ("ok", "ligado 22 C, GREE")

    with context["app"].state.sessions() as session:
        stored = session.get(Device, context["device"])
        stored.last_seen_at = datetime.now(UTC) - OFFLINE_AFTER - timedelta(seconds=1)
        session.commit()
    offline = client.get(devices_url, headers=context["professor_headers"]).json()[0]
    assert offline["online"] is False
    assert offline["seconds_since_contact"] > 150


def test_invalid_token_does_not_touch_any_device(context):
    client = context["client"]
    wrong = {"Authorization": "Bearer token-invalido", **DIAGNOSTIC_HEADERS}
    assert client.get("/devices/me/control", headers=wrong).status_code == 401
    device = client.get(
        f"/rooms/{context['room']}/devices", headers=context["professor_headers"]
    ).json()[0]
    assert device["last_seen_at"] is None
