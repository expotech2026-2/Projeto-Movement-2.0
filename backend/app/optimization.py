from dataclasses import dataclass
from typing import Protocol

import numpy as np
from scipy.optimize import Bounds, LinearConstraint, milp
from sqlalchemy import text
from sqlalchemy.orm import Session

INTERVALS: tuple[int, ...] = (15, 30, 60, 90, 120, 300)
BASELINE_INTERVAL = 16
OCCUPIED_THRESHOLD = 0.5
OCCUPIED_MAX_INTERVAL = 90
LOCAL_TZ = "America/Sao_Paulo"
DEFAULT_OCCUPIED_HOURS = frozenset({7, 8, 9, 10, 11, 13, 14, 15, 16, 19, 20, 21})
SECONDS_PER_HOUR = 3600
INFEASIBLE_MESSAGE = "Orçamento insuficiente para manter leituras frescas nas horas ocupadas"

# Cada par de leituras consecutivas conta na hora (São Paulo) da segunda leitura.
HOURLY_PROFILE = text("""
    WITH ordered AS (
        SELECT measured_at, occupancy, temp_inside,
               lag(temp_inside) OVER w AS prev_temp,
               lag(measured_at) OVER w AS prev_at
        FROM sensor_readings
        WHERE room_id = :room_id
        WINDOW w AS (ORDER BY measured_at)
    )
    SELECT extract(hour FROM measured_at AT TIME ZONE 'America/Sao_Paulo')::int AS hour,
           avg((occupancy > 0)::int) AS occupancy,
           percentile_cont(0.95) WITHIN GROUP (
               ORDER BY abs(temp_inside - prev_temp) / extract(epoch FROM measured_at - prev_at)
           ) AS temp_rate
    FROM ordered
    WHERE prev_at IS NOT NULL AND measured_at > prev_at
    GROUP BY 1
    ORDER BY 1
""")


class InfeasiblePlan(ValueError):
    pass


@dataclass(frozen=True)
class HourProfile:
    hour: int
    occupancy: float
    temp_rate: float
    source: str


@dataclass(frozen=True)
class SamplingPlan:
    intervals: list[int]
    energy_j: float
    expected_error_c: float


def default_profile() -> list[HourProfile]:
    return [
        HourProfile(hour, 0.8, 0.002, "default")
        if hour in DEFAULT_OCCUPIED_HOURS
        else HourProfile(hour, 0.0, 0.0005, "default")
        for hour in range(24)
    ]


def daily_energy(intervals: list[int], energy_per_send_j: float) -> float:
    return sum(SECONDS_PER_HOUR / seconds * energy_per_send_j for seconds in intervals)


def expected_error(profile: list[HourProfile], intervals: list[int]) -> float:
    return sum(
        hour.occupancy * hour.temp_rate * seconds
        for hour, seconds in zip(profile, intervals, strict=True)
    )


def plan_sampling(
    profile: list[HourProfile],
    energy_per_send_j: float,
    daily_budget_j: float,
    energy_weight: float = 1e-4,
) -> SamplingPlan:
    hours, options = len(profile), len(INTERVALS)
    durations = np.array(INTERVALS, dtype=float)
    energy = np.tile(SECONDS_PER_HOUR / durations * energy_per_send_j, (hours, 1))
    error = np.array([[hour.occupancy * hour.temp_rate * d for d in INTERVALS] for hour in profile])
    upper = np.ones((hours, options))
    for index, hour in enumerate(profile):
        if hour.occupancy >= OCCUPIED_THRESHOLD:
            upper[index, durations > OCCUPIED_MAX_INTERVAL] = 0
    result = milp(
        c=(error + energy_weight * energy).ravel(),
        constraints=[
            LinearConstraint(np.kron(np.eye(hours), np.ones(options)), 1, 1),
            LinearConstraint(energy.ravel(), 0, daily_budget_j),
        ],
        integrality=np.ones(hours * options),
        bounds=Bounds(0, upper.ravel()),
    )
    if not result.success:
        raise InfeasiblePlan(INFEASIBLE_MESSAGE)
    chosen = result.x.reshape(hours, options).argmax(axis=1)
    intervals = [INTERVALS[option] for option in chosen]
    return SamplingPlan(
        intervals, daily_energy(intervals, energy_per_send_j), expected_error(profile, intervals)
    )


def hourly_profile(session: Session, room_id: str) -> list[HourProfile]:
    observed = {
        row.hour: HourProfile(row.hour, float(row.occupancy), float(row.temp_rate), "history")
        for row in session.execute(HOURLY_PROFILE, {"room_id": room_id})
    }
    return [observed.get(hour.hour, hour) for hour in default_profile()]


class IntervalPolicy(Protocol):
    def intervals(self, profile: list[HourProfile]) -> list[int]: ...


class FixedIntervalPolicy:
    def __init__(self, seconds: int = BASELINE_INTERVAL):
        self.seconds = seconds

    def intervals(self, profile: list[HourProfile]) -> list[int]:
        return [self.seconds] * len(profile)


class OptimizedIntervalPolicy:
    def __init__(self, energy_per_send_j: float, daily_budget_j: float):
        self.energy_per_send_j = energy_per_send_j
        self.daily_budget_j = daily_budget_j

    def intervals(self, profile: list[HourProfile]) -> list[int]:
        return plan_sampling(profile, self.energy_per_send_j, self.daily_budget_j).intervals


def build_plan(
    policy: IntervalPolicy, profile: list[HourProfile], energy_per_send_j: float
) -> SamplingPlan:
    intervals = policy.intervals(profile)
    return SamplingPlan(
        intervals, daily_energy(intervals, energy_per_send_j), expected_error(profile, intervals)
    )
