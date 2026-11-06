from datetime import UTC, datetime, timedelta
from uuid import uuid4
from zoneinfo import ZoneInfo

import pytest


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


def test_professor_reads_plan_with_default_profile(context):
    response = plan(context)
    assert response.status_code == 200
    body = response.json()
    assert len(body["hours"]) == 24
    assert {hour["source"] for hour in body["hours"]} == {"default"}
    assert body["energy_j"] <= body["budget_j"]
    assert body["saving_percent"] > 0
    assert body["baseline_energy_j"] == pytest.approx(1728.0)


def test_plan_requires_session(context):
    response = context["client"].get(f"/rooms/{context['room']}/sampling-plan")
    assert response.status_code == 401


def test_plan_for_unknown_room_returns_404(context):
    response = context["client"].get(
        "/rooms/nao-existe/sampling-plan", headers=context["professor_headers"]
    )
    assert response.status_code == 404


def test_plan_rejects_infeasible_budget(context):
    response = plan(context, budget_ratio=0.05)
    assert response.status_code == 422
    assert "Orçamento insuficiente" in response.json()["detail"]


def test_history_replaces_default_for_observed_hour(context):
    now = datetime.now(UTC)
    first_at, second_at = now - timedelta(seconds=120), now - timedelta(seconds=60)
    first = sample(measured_at=first_at.isoformat(), occupancy=5, temp_inside=25.0)
    second = sample(measured_at=second_at.isoformat(), occupancy=5, temp_inside=25.6)
    assert publish(context, first).status_code == 201
    assert publish(context, second).status_code == 201
    hour = second_at.astimezone(ZoneInfo("America/Sao_Paulo")).hour
    observed = plan(context).json()["hours"][hour]
    assert observed["source"] == "history"
    assert observed["occupancy"] == 1.0
    assert observed["temp_rate"] == pytest.approx(0.01)


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
