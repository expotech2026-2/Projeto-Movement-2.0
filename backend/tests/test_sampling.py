from datetime import UTC, datetime, timedelta
from uuid import uuid4
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy import text


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


def plan(context, **params):
    return context["client"].get(
        f"/rooms/{context['room']}/sampling-plan",
        params=params,
        headers=context["professor_headers"],
    )


def previous_hour_start() -> datetime:
    return (datetime.now(UTC) - timedelta(hours=1)).replace(minute=5, second=0, microsecond=0)


def publish_series(context, start, count=7, step=30, temp_step=0.3, occupancy=5):
    for index in range(count):
        payload = sample(
            measured_at=(start + timedelta(seconds=step * index)).isoformat(),
            occupancy=occupancy,
            temp_inside=25.0 + temp_step * index,
        )
        assert publish(context, payload).status_code == 201


def test_plan_without_real_readings_shows_no_numbers(context):
    response = plan(context)
    assert response.status_code == 200
    body = response.json()
    assert body["observed_hours"] == 0
    assert len(body["hours"]) == 24
    assert {hour["source"] for hour in body["hours"]} == {"missing"}
    assert {hour["interval_seconds"] for hour in body["hours"]} == {None}
    assert body["energy_j"] is None
    assert body["saving_percent"] is None
    assert body["expected_error_c"] is None


def test_plan_requires_session(context):
    response = context["client"].get(f"/rooms/{context['room']}/sampling-plan")
    assert response.status_code == 401


def test_plan_for_unknown_room_returns_404(context):
    response = context["client"].get(
        "/rooms/nao-existe/sampling-plan", headers=context["professor_headers"]
    )
    assert response.status_code == 404


def test_plan_rejects_infeasible_budget(context):
    publish_series(context, previous_hour_start())
    response = plan(context, budget_ratio=0.05)
    assert response.status_code == 422
    assert "Orçamento insuficiente" in response.json()["detail"]


def test_plan_uses_only_hours_with_real_readings(context):
    start = previous_hour_start()
    publish_series(context, start)
    hour = start.astimezone(ZoneInfo("America/Sao_Paulo")).hour
    body = plan(context).json()
    assert body["observed_hours"] == 1
    observed = body["hours"][hour]
    assert observed["source"] == "history"
    assert observed["occupancy"] == 1.0
    assert observed["temp_rate"] == pytest.approx(0.01)
    assert observed["interval_seconds"] <= 90
    others = [item for item in body["hours"] if item["hour"] != hour]
    assert {item["source"] for item in others} == {"missing"}
    assert {item["interval_seconds"] for item in others} == {None}
    assert body["baseline_energy_j"] == pytest.approx(72.0)
    assert body["energy_j"] <= body["budget_j"]


def test_hour_with_too_few_readings_stays_out_of_plan(context):
    publish_series(context, previous_hour_start(), count=3)
    assert plan(context).json()["observed_hours"] == 0


def test_readings_far_apart_do_not_estimate_rate(context):
    publish_series(context, datetime.now(UTC) - timedelta(hours=8), count=8, step=1200)
    assert plan(context).json()["observed_hours"] == 0


def test_sensor_failure_does_not_enter_profile(context):
    start = previous_hour_start()
    publish_series(context, start, count=4)
    with context["app"].state.sessions() as session:
        session.execute(
            text("""
                INSERT INTO sensor_readings (id, message_id, device_id, room_id, measured_at,
                    received_at, occupancy, temp_inside, temp_outside, target_temp,
                    humidity_inside, humidity_outside, ac_on, manual_mode)
                SELECT gen_random_uuid(), gen_random_uuid(), :device, :room,
                    :start + make_interval(secs => 120 + 30 * n), now(), 5, 0, 19, 21, 0, 60,
                    false, true
                FROM generate_series(0, 3) AS n
            """),
            {"device": context["device"], "room": context["room"], "start": start},
        )
        session.commit()
    assert plan(context).json()["observed_hours"] == 0


def test_device_without_history_keeps_fixed_interval(context):
    response = context["client"].get(
        "/devices/me/sampling-interval", headers=context["device_headers"]
    )
    assert response.status_code == 200
    assert response.json()["interval_seconds"] == 16


def test_device_reads_current_interval(context):
    response = context["client"].get(
        "/devices/me/sampling-interval", headers=context["device_headers"]
    )
    assert response.status_code == 200
    body = response.json()
    assert 0 <= body["hour"] <= 23
    assert 15 <= body["interval_seconds"] <= 300


def test_device_with_invalid_token_is_rejected(context):
    response = context["client"].get(
        "/devices/me/sampling-interval", headers={"Authorization": "Bearer invalido"}
    )
    assert response.status_code == 401
