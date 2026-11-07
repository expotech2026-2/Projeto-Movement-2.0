"""Comando do ar-condicionado pelo site: o professor escolhe, o ESP32 busca e aplica."""

from datetime import UTC, datetime, timedelta
from typing import Literal

from fastapi import APIRouter, Depends
from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator
from sqlalchemy.orm import Session

from app.climate import ClimateService
from app.dependencies import Climate, CurrentDevice, CurrentUser, Db, require_user
from app.management import get_room
from app.models import Room, Unit

MANUAL_DURATION = timedelta(hours=2)
Mode = Literal["auto", "manual", "off"]


class ControlInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    mode: Mode
    target: int | None = Field(default=None, ge=16, le=30, strict=True)

    @model_validator(mode="after")
    def target_only_for_manual(self) -> "ControlInput":
        if self.mode == "manual" and self.target is None:
            raise ValueError("Informe a temperatura (16 a 30 °C) para o modo manual")
        if self.mode != "manual":
            self.target = None
        return self


class OutsideOutput(BaseModel):
    city: str
    temperature: float
    humidity: float
    source: str


class ControlOutput(BaseModel):
    mode: Mode
    target: int | None
    version: int
    changed_by: str | None
    changed_at: AwareDatetime | None
    expires_at: AwareDatetime | None
    outside: OutsideOutput | None


class DeviceControlOutput(BaseModel):
    version: int
    mode: Mode
    target: int | None
    remaining_seconds: int
    temp_outside: float | None
    humidity_outside: float | None


def effective(room: Room, now: datetime) -> tuple[str, int | None, datetime | None]:
    """Modo em vigor: um comando manual ou de desligar volta ao automático depois de 2 h."""
    if room.ac_mode == "auto" or room.ac_changed_at is None:
        return "auto", None, None
    expires = room.ac_changed_at + MANUAL_DURATION
    if now >= expires:
        return "auto", None, None
    return room.ac_mode, room.ac_target, expires


def outside_for(session: Session, room: Room, climate: ClimateService) -> OutsideOutput | None:
    unit = session.get(Unit, room.unit_id)
    if unit is None or unit.latitude is None or unit.longitude is None:
        return None
    value = climate.outside(unit.latitude, unit.longitude)
    if value is None:
        return None
    return OutsideOutput(
        city=unit.city,
        temperature=value.temperature,
        humidity=value.humidity,
        source=value.source,
    )


def control_output(session: Session, room: Room, climate: ClimateService) -> ControlOutput:
    mode, target, expires = effective(room, datetime.now(UTC))
    return ControlOutput(
        mode=mode,
        target=target,
        version=room.ac_version,
        changed_by=room.ac_changed_by,
        changed_at=room.ac_changed_at,
        expires_at=expires,
        outside=outside_for(session, room, climate),
    )


def create_control_router() -> APIRouter:
    router = APIRouter(tags=["Controle do ar-condicionado"])

    @router.get(
        "/rooms/{room_id}/control",
        response_model=ControlOutput,
        dependencies=[Depends(require_user)],
    )
    def control(room_id: str, session: Db, climate: Climate):
        return control_output(session, get_room(session, room_id), climate)

    # Professores também comandam: é a exceção à regra de escrita só para administradores.
    @router.put("/rooms/{room_id}/control", response_model=ControlOutput)
    def set_control(
        room_id: str, payload: ControlInput, session: Db, principal: CurrentUser, climate: Climate
    ):
        room = get_room(session, room_id)
        room.ac_mode = payload.mode
        room.ac_target = payload.target
        room.ac_version += 1
        room.ac_changed_by = principal.username
        room.ac_changed_at = datetime.now(UTC)
        session.commit()
        return control_output(session, room, climate)

    @router.get("/devices/me/control", response_model=DeviceControlOutput)
    def device_control(device: CurrentDevice, session: Db, climate: Climate):
        room = get_room(session, device.room_id)
        now = datetime.now(UTC)
        mode, target, expires = effective(room, now)
        outside = outside_for(session, room, climate)
        return DeviceControlOutput(
            version=room.ac_version,
            mode=mode,
            target=target,
            remaining_seconds=int((expires - now).total_seconds()) if expires else 0,
            temp_outside=outside.temperature if outside else None,
            humidity_outside=outside.humidity if outside else None,
        )

    return router
