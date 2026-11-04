from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, date, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import event, func, select

from app.models import MonthlySummary, SensorReading
from app.retention import consolidate, monthly_history


def add_reading(session, context, at, temperature=25, ac_on=True):
    reading = SensorReading(
        message_id=uuid4(),
        device_id=context["device"],
        room_id=context["room"],
        measured_at=at,
        occupancy=10,
        temp_inside=temperature,
        temp_outside=30,
        humidity_inside=50,
        humidity_outside=60,
        target_temp=23,
        ac_on=ac_on,
        manual_mode=False,
    )
    session.add(reading)
    session.commit()
    return reading.id


def test_batches_preserve_weighted_mean_and_retries_do_not_double_count(context):
    sessions = context["app"].state.sessions
    now = datetime.now(UTC)
    old = (now - timedelta(days=65)).replace(day=15, hour=12)
    with sessions() as session:
        add_reading(session, context, old, 20, False)
        add_reading(session, context, old + timedelta(minutes=1), 30)
        recent = add_reading(session, context, now, 22)
        consolidate(session, now)
        add_reading(session, context, old + timedelta(minutes=2), 40)
        consolidate(session, now)
        consolidate(session, now)
        summary = session.scalar(
            select(MonthlySummary).where(MonthlySummary.room_id == context["room"])
        )
        assert summary.sample_count == 3
        assert summary.avg_temp_inside == 30
        assert summary.ac_on_percent == pytest.approx(200 / 3)
        assert session.get(SensorReading, recent) is not None
        rows = monthly_history(session, context["room"])
        assert sum(row["sample_count"] for row in rows) == 4
        assert rows[-1]["avg_temp_inside"] == 30


def test_exact_30_day_boundary_and_local_calendar_month(context):
    sessions = context["app"].state.sessions
    now = datetime(2026, 11, 4, 12, tzinfo=UTC)
    with sessions() as session:
        boundary = add_reading(session, context, now - timedelta(days=30))
        expired = add_reading(session, context, now - timedelta(days=30, microseconds=1))
        add_reading(session, context, datetime(2026, 10, 1, 2, 59, tzinfo=UTC), 20)
        add_reading(session, context, datetime(2026, 10, 1, 3, 0, tzinfo=UTC), 30)
        consolidate(session, now)
        assert session.get(SensorReading, boundary) is not None
        assert session.get(SensorReading, expired) is None
        summaries = {
            row.month: row
            for row in session.scalars(
                select(MonthlySummary).where(MonthlySummary.room_id == context["room"])
            )
        }
        assert summaries[date(2026, 9, 1)].avg_temp_inside == 20
        assert summaries[date(2026, 10, 1)].sample_count == 2


def test_monthly_query_combines_archived_and_recent_samples_from_same_month(context):
    sessions = context["app"].state.sessions
    with sessions() as session:
        add_reading(session, context, datetime(2026, 10, 1, 12, tzinfo=UTC), 20)
        add_reading(session, context, datetime(2026, 10, 10, 12, tzinfo=UTC), 40)
        consolidate(session, datetime(2026, 11, 4, 12, tzinfo=UTC))
        row = next(
            item
            for item in monthly_history(
                session, context["room"], datetime(2026, 11, 4, 12, tzinfo=UTC)
            )
            if item["month"] == date(2026, 10, 1)
        )
        assert row["sample_count"] == 2
        assert row["avg_temp_inside"] == 30
        assert row["finalized"] is False


def test_summary_expires_12_months_after_end_of_month(context):
    sessions = context["app"].state.sessions
    with sessions() as session:
        add_reading(session, context, datetime(2025, 9, 15, tzinfo=UTC))
        consolidate(session, datetime(2026, 9, 30, 12, tzinfo=UTC))
        assert (
            session.scalar(
                select(func.count())
                .select_from(MonthlySummary)
                .where(MonthlySummary.room_id == context["room"])
            )
            == 1
        )
        consolidate(session, datetime(2026, 10, 1, 3, tzinfo=UTC))
        assert (
            session.scalar(
                select(func.count())
                .select_from(MonthlySummary)
                .where(MonthlySummary.room_id == context["room"])
            )
            == 0
        )


def test_concurrent_consolidations_consume_readings_once(context):
    sessions = context["app"].state.sessions
    now = datetime.now(UTC)
    with sessions() as session:
        add_reading(session, context, now - timedelta(days=50))

    def run(_):
        with sessions() as session:
            consolidate(session, now)

    with ThreadPoolExecutor(max_workers=3) as pool:
        list(pool.map(run, range(3)))
    with sessions() as session:
        assert (
            session.scalar(
                select(MonthlySummary).where(MonthlySummary.room_id == context["room"])
            ).sample_count
            == 1
        )


def test_failed_aggregation_rolls_back_reading_removal(context):
    sessions = context["app"].state.sessions
    now = datetime.now(UTC)
    with sessions() as session:
        reading_id = add_reading(session, context, now - timedelta(days=50))
    engine = sessions.kw["bind"]

    def fail_after_delete(
        connection, cursor, statement, parameters, execution_context, executemany
    ):
        if "INSERT INTO monthly_summaries" in statement:
            raise RuntimeError("Simulated database failure")

    event.listen(engine, "after_cursor_execute", fail_after_delete)
    try:
        with sessions() as session, pytest.raises(RuntimeError):
            consolidate(session, now)
    finally:
        event.remove(engine, "after_cursor_execute", fail_after_delete)
    with sessions() as session:
        assert session.get(SensorReading, reading_id) is not None
