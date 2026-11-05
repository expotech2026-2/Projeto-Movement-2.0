from datetime import UTC, datetime
from uuid import uuid4

from app.dependencies import telemetry_repository
from app.models import SensorReading


class InMemoryTelemetryRepository:
    def __init__(self, reading: SensorReading):
        self.reading = reading

    def save(self, device, payload):
        raise NotImplementedError

    def latest(self, room_id):
        return self.reading

    def history(self, room_id, limit, since):
        return [self.reading]


def test_latest_uses_injected_repository(context):
    now = datetime.now(UTC)
    reading = SensorReading(
        id=uuid4(),
        message_id=uuid4(),
        device_id=context["device"],
        room_id=context["room"],
        measured_at=now,
        received_at=now,
        occupancy=3,
        temp_inside=22.0,
        temp_outside=30.0,
        target_temp=22.0,
        humidity_inside=50.0,
        humidity_outside=60.0,
        ac_on=True,
        manual_mode=False,
    )
    overrides = context["app"].dependency_overrides
    overrides[telemetry_repository] = lambda: InMemoryTelemetryRepository(reading)
    try:
        response = context["client"].get(
            f"/rooms/{context['room']}/latest", headers=context["professor_headers"]
        )
        history = context["client"].get(
            f"/rooms/{context['room']}/history", headers=context["professor_headers"]
        )
    finally:
        overrides.clear()
    assert response.status_code == 200
    assert response.json()["reading"]["temp_inside"] == 22.0
    assert response.json()["reading"]["occupancy"] == 3
    assert [item["temp_inside"] for item in history.json()] == [22.0]
