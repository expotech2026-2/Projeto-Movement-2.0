from datetime import UTC, datetime
from uuid import uuid4

from app.events import TelemetrySubject


def sample(**changes):
    return {
        "message_id": str(uuid4()),
        "measured_at": datetime.now(UTC).isoformat(),
        "occupancy": 8,
        "temp_inside": 27.5,
        "temp_outside": 32.0,
        "target_temp": 21.0,
        "humidity_inside": 55.0,
        "humidity_outside": 62.0,
        "ac_on": False,
        "manual_mode": True,
        **changes,
    }


def publish(context, payload):
    return context["client"].post("/telemetry", json=payload, headers=context["device_headers"])


def alerts(context):
    response = context["client"].get(
        f"/rooms/{context['room']}/alerts", headers=context["professor_headers"]
    )
    assert response.status_code == 200
    return response.json()


def test_hot_occupied_room_creates_comfort_alert(context):
    assert publish(context, sample(temp_inside=29.5, occupancy=8)).status_code == 201
    [alert] = alerts(context)
    assert alert["kind"] == "conforto"
    assert alert["value"] == 29.5
    assert "29,5 °C" in alert["message"]


def test_hot_empty_room_creates_no_alert(context):
    assert publish(context, sample(temp_inside=29.5, occupancy=0)).status_code == 201
    assert alerts(context) == []


def test_humid_room_creates_humidity_alert(context):
    assert publish(context, sample(humidity_inside=75.0)).status_code == 201
    [alert] = alerts(context)
    assert alert["kind"] == "umidade"
    assert alert["value"] == 75.0


def test_normal_reading_creates_no_alert(context):
    assert publish(context, sample()).status_code == 201
    assert alerts(context) == []


def test_duplicate_reading_does_not_repeat_alert(context):
    payload = sample(temp_inside=29.5)
    assert publish(context, payload).status_code == 201
    assert publish(context, payload).status_code == 200
    assert len(alerts(context)) == 1


def test_alerts_for_unknown_room_return_404(context):
    response = context["client"].get(
        "/rooms/nao-existe/alerts", headers=context["professor_headers"]
    )
    assert response.status_code == 404


def test_subject_notifies_attached_observers_in_order():
    calls = []

    class Recorder:
        def __init__(self, name):
            self.name = name

        def on_reading(self, session, reading):
            calls.append((self.name, session, reading))

    subject = TelemetrySubject()
    subject.attach(Recorder("primeiro"))
    subject.attach(Recorder("segundo"))
    subject.notify("sessao", "leitura")
    assert calls == [("primeiro", "sessao", "leitura"), ("segundo", "sessao", "leitura")]
