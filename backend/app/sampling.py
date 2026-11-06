from datetime import datetime
from typing import Annotated
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel

from app.dependencies import CurrentDevice, Db, require_user
from app.optimization import (
    LOCAL_TZ,
    FixedIntervalPolicy,
    InfeasiblePlan,
    OptimizedIntervalPolicy,
    build_plan,
    hourly_profile,
)
from app.repository import room_exists


class SamplingHour(BaseModel):
    hour: int
    interval_seconds: int
    occupancy: float
    temp_rate: float
    source: str


class SamplingPlanResponse(BaseModel):
    hours: list[SamplingHour]
    energy_j: float
    baseline_energy_j: float
    budget_j: float
    saving_percent: float
    expected_error_c: float
    baseline_error_c: float
    energy_per_send_j: float


class SamplingIntervalResponse(BaseModel):
    hour: int
    interval_seconds: int


def create_sampling_router() -> APIRouter:
    router = APIRouter(tags=["Plano de leitura"])

    @router.get(
        "/rooms/{room_id}/sampling-plan",
        response_model=SamplingPlanResponse,
        dependencies=[Depends(require_user)],
    )
    def sampling_plan(
        room_id: str,
        request: Request,
        session: Db,
        budget_ratio: Annotated[float, Query(gt=0, le=1)] = 0.5,
    ):
        if not room_exists(session, room_id):
            raise HTTPException(404, "Ambiente não encontrado")
        energy = request.app.state.settings.energy_per_send_j
        profile = hourly_profile(session, room_id)
        baseline = build_plan(FixedIntervalPolicy(), profile, energy)
        budget = budget_ratio * baseline.energy_j
        try:
            plan = build_plan(OptimizedIntervalPolicy(energy, budget), profile, energy)
        except InfeasiblePlan as error:
            raise HTTPException(422, str(error)) from None
        return SamplingPlanResponse(
            hours=[
                SamplingHour(
                    hour=hour.hour,
                    interval_seconds=seconds,
                    occupancy=hour.occupancy,
                    temp_rate=hour.temp_rate,
                    source=hour.source,
                )
                for hour, seconds in zip(profile, plan.intervals, strict=True)
            ],
            energy_j=round(plan.energy_j, 1),
            baseline_energy_j=round(baseline.energy_j, 1),
            budget_j=round(budget, 1),
            saving_percent=round(100 * (1 - plan.energy_j / baseline.energy_j), 1),
            expected_error_c=round(plan.expected_error_c, 3),
            baseline_error_c=round(baseline.expected_error_c, 3),
            energy_per_send_j=energy,
        )

    @router.get("/devices/me/sampling-interval", response_model=SamplingIntervalResponse)
    def sampling_interval(device: CurrentDevice, request: Request, session: Db):
        settings = request.app.state.settings
        profile = hourly_profile(session, device.room_id)
        baseline = build_plan(FixedIntervalPolicy(), profile, settings.energy_per_send_j)
        budget = settings.sampling_budget_ratio * baseline.energy_j
        try:
            intervals = OptimizedIntervalPolicy(settings.energy_per_send_j, budget).intervals(
                profile
            )
        except InfeasiblePlan:
            intervals = FixedIntervalPolicy().intervals(profile)
        hour = datetime.now(ZoneInfo(LOCAL_TZ)).hour
        return SamplingIntervalResponse(hour=hour, interval_seconds=intervals[hour])

    return router
