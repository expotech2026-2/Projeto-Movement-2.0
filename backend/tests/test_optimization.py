import pytest

from app.optimization import (
    DEFAULT_OCCUPIED_HOURS,
    INTERVALS,
    FixedIntervalPolicy,
    HourProfile,
    InfeasiblePlan,
    OptimizedIntervalPolicy,
    build_plan,
    daily_energy,
    default_profile,
    plan_sampling,
)

ENERGY = 0.32
BASELINE = daily_energy([16] * 24, ENERGY)


def test_generous_budget_samples_fast_when_occupied_and_slow_when_empty():
    plan = plan_sampling(default_profile(), ENERGY, 1e9)
    for hour, seconds in enumerate(plan.intervals):
        assert seconds == (15 if hour in DEFAULT_OCCUPIED_HOURS else 300)


def test_occupied_hours_never_exceed_freshness_limit():
    profile = default_profile()
    plan = plan_sampling(profile, ENERGY, 0.2 * BASELINE)
    for hour, seconds in zip(profile, plan.intervals, strict=True):
        if hour.occupancy >= 0.5:
            assert seconds <= 90


def test_plan_respects_energy_budget():
    plan = plan_sampling(default_profile(), ENERGY, 518.4)
    assert plan.energy_j <= 518.4 + 1e-6


def test_infeasible_budget_raises():
    with pytest.raises(InfeasiblePlan):
        plan_sampling(default_profile(), ENERGY, 100)


def test_tight_budget_prioritizes_faster_changing_hour():
    profile = [HourProfile(hour, 0.0, 0.0, "default") for hour in range(24)]
    profile[10] = HourProfile(10, 0.8, 0.004, "default")
    profile[11] = HourProfile(11, 0.8, 0.001, "default")
    plan = plan_sampling(profile, 1.0, 564)
    assert plan.intervals[10] == 15
    assert plan.intervals[11] == 60
    assert all(plan.intervals[hour] == 300 for hour in range(24) if hour not in (10, 11))


def test_fixed_policy_reproduces_current_firmware():
    plan = build_plan(FixedIntervalPolicy(), default_profile(), ENERGY)
    assert plan.intervals == [16] * 24
    assert plan.energy_j == pytest.approx(1728.0)


def test_policies_share_the_same_interface():
    profile = default_profile()
    fixed = build_plan(FixedIntervalPolicy(), profile, ENERGY)
    optimized = build_plan(OptimizedIntervalPolicy(ENERGY, 0.5 * BASELINE), profile, ENERGY)
    assert len(fixed.intervals) == len(optimized.intervals) == 24
    assert set(optimized.intervals) <= set(INTERVALS)
    assert optimized.energy_j < fixed.energy_j
    assert optimized.energy_j == pytest.approx(852.5, abs=0.1)
    assert optimized.expected_error_c == pytest.approx(0.36, abs=1e-3)
