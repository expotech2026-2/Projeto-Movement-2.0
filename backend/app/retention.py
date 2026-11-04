import asyncio
import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import text
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)
METRICS = (
    "temp_inside",
    "temp_outside",
    "humidity_inside",
    "humidity_outside",
    "occupancy",
    "ac_on",
)


def consolidate(session: Session, now: datetime | None = None) -> dict:
    now = now or datetime.now(UTC)
    cutoff = now - timedelta(days=30)
    session.execute(text("SELECT pg_advisory_xact_lock(726031)"))
    sums = ", ".join(f"{metric}_sum" for metric in METRICS)
    aggregates = ", ".join(
        f"sum({metric}::{'int' if metric == 'ac_on' else 'float8'})" for metric in METRICS
    )
    updates = ", ".join(f"{m}_sum = monthly_summaries.{m}_sum + EXCLUDED.{m}_sum" for m in METRICS)
    statement = text(f"""
        WITH expired AS (
            DELETE FROM sensor_readings WHERE measured_at < :cutoff RETURNING *
        ), grouped AS (
            SELECT room_id,
                date_trunc('month', measured_at AT TIME ZONE 'America/Sao_Paulo')::date AS month,
                count(*) AS sample_count, {aggregates}
            FROM expired GROUP BY room_id, month
        )
        INSERT INTO monthly_summaries (room_id, month, sample_count, {sums})
        SELECT * FROM grouped
        ON CONFLICT (room_id, month) DO UPDATE SET
            sample_count = monthly_summaries.sample_count + EXCLUDED.sample_count, {updates}
    """)
    result = session.execute(statement, {"cutoff": cutoff})
    removed = session.execute(
        text("""
        DELETE FROM monthly_summaries
        WHERE month + interval '13 months' <= (:now AT TIME ZONE 'America/Sao_Paulo')
    """),
        {"now": now},
    )
    session.commit()
    return {"groups_updated": result.rowcount, "summaries_removed": removed.rowcount}


def monthly_history(session: Session, room_id: str, now: datetime | None = None) -> list[dict]:
    sums = ", ".join(f"{metric}_sum" for metric in METRICS)
    raw_sums = ", ".join(
        f"sum({metric}::{'int' if metric == 'ac_on' else 'float8'}) AS {metric}_sum"
        for metric in METRICS
    )
    averages = ", ".join(
        f"{'100.0 * ' if metric == 'ac_on' else ''}sum({metric}_sum) / sum(sample_count) "
        f"AS {'ac_on_percent' if metric == 'ac_on' else 'avg_' + metric}"
        for metric in METRICS
    )
    rows = session.execute(
        text(f"""
        WITH parts AS (
            SELECT month, sample_count, {sums} FROM monthly_summaries WHERE room_id = :room
            UNION ALL
            SELECT date_trunc('month', measured_at AT TIME ZONE 'America/Sao_Paulo')::date,
                count(*), {raw_sums} FROM sensor_readings WHERE room_id = :room GROUP BY 1
        )
        SELECT month, sum(sample_count)::bigint AS sample_count, {averages},
            month + interval '1 month' <=
                (:now AT TIME ZONE 'America/Sao_Paulo') - interval '30 days' AS finalized
        FROM parts WHERE month + interval '13 months' > (:now AT TIME ZONE 'America/Sao_Paulo')
        GROUP BY month ORDER BY month DESC LIMIT 13
    """),
        {"room": room_id, "now": now or datetime.now(UTC)},
    )
    return [dict(row) for row in rows.mappings()]


async def retention_loop(sessions, interval_seconds: int):
    while True:
        try:

            def run():
                with sessions() as session:
                    consolidate(session)

            await asyncio.to_thread(run)
        except Exception:
            logger.exception("Falha na consolidação; transação revertida e nova tentativa agendada")
        await asyncio.sleep(interval_seconds)
