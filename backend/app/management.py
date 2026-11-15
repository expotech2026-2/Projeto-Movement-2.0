import secrets
from datetime import UTC, date, datetime
from typing import Annotated, Literal
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, computed_field
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.climate import UF_BY_NAME, ClimateService, ClimateUnavailable, split_city
from app.dependencies import Climate, Db, require_admin, require_user
from app.device_status import is_online
from app.ir_protocols import brand_candidate, lookup
from app.models import DEFAULT_UNIT_ID, DEFAULT_UNIT_NAME, AirConditioner, Device, Room, Unit
from app.retention import monthly_history
from app.security import hash_device_token

Admin = [Depends(require_admin)]


class UnitInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    name: str = Field(min_length=1, max_length=120)
    address: str = Field(default="", max_length=160)
    city: str = Field(default="", max_length=120)


class UnitOutput(UnitInput):
    model_config = ConfigDict(from_attributes=True)
    id: str
    room_count: int = 0
    latitude: float | None = None
    longitude: float | None = None


class RoomInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    unit_id: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=120)
    location: str = Field(default="", max_length=120)
    capacity: int = Field(default=1, ge=1, le=10000, strict=True)
    computers: int = Field(default=0, ge=0, le=10000, strict=True)
    area_m2: float | None = Field(default=None, ge=1, le=100000, allow_inf_nan=False)
    ceiling_height_m: float = Field(default=3.0, ge=2, le=20, allow_inf_nan=False)


AREA_PER_PERSON_M2 = 1.5  # sala de aula, quando a área não é informada
MIN_VOLUME_M3 = 20.0


def room_volume(area_m2: float | None, ceiling_height_m: float, capacity: int) -> float:
    """Volume de ar da sala para o cálculo do ESP32: área informada ou estimada pela capacidade."""
    area = area_m2 or capacity * AREA_PER_PERSON_M2
    return round(max(area * ceiling_height_m, MIN_VOLUME_M3), 1)


class RoomOutput(RoomInput):
    model_config = ConfigDict(from_attributes=True)
    id: str
    appliance_count: int = 0

    @computed_field
    @property
    def volume_m3(self) -> float:
        return room_volume(self.area_m2, self.ceiling_height_m, self.capacity)


class ApplianceInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    name: str = Field(min_length=1, max_length=120)
    kind: Literal["split", "janela", "cassete", "piso_teto", "portatil", "vrf"]
    brand: str = Field(default="", max_length=80)
    model: str = Field(default="", max_length=80)
    capacity_btu: int = Field(ge=1000, le=500000, strict=True)
    inverter: bool = Field(default=False, strict=True)
    status: Literal["ativo", "manutencao", "inativo"] = "ativo"
    ir_protocol: (
        Literal[
            "LG",
            "LG2",
            "GREE",
            "SAMSUNG_AC",
            "MIDEA",
            "COOLIX",
            "DAIKIN",
            "FUJITSU_AC",
            "HITACHI_AC",
            "WHIRLPOOL_AC",
            "TCL112AC",
            "KELVINATOR",
            "MIRAGE",
            "NEOCLIMA",
        ]
        | None
    ) = None
    ir_model: int = Field(default=1, ge=1, le=6, strict=True)


class ApplianceOutput(ApplianceInput):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    room_id: str
    ir_source: str


def resolve_appliance_ir(appliance: AirConditioner) -> None:
    match = lookup(appliance.brand, appliance.model)
    if appliance.ir_protocol:
        appliance.ir_source = (
            match["confidence"]
            if match
            and (appliance.ir_protocol, appliance.ir_model)
            == (match["protocol"], match["ir_model"])
            else "manual"
        )
        return
    match = match or brand_candidate(appliance.brand)
    appliance.ir_protocol = match["protocol"] if match else None
    appliance.ir_model = match["ir_model"] if match else 1
    appliance.ir_source = match["confidence"] if match else "pending"


class DeviceOutput(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    room_id: str
    enabled: bool
    last_seen_at: AwareDatetime | None = None
    firmware: str | None = None
    rssi: int | None = None
    uptime_seconds: int | None = None
    sensor_faults: str | None = None
    ac_state: str | None = None

    @computed_field
    @property
    def online(self) -> bool:
        return is_online(self.last_seen_at, datetime.now(UTC))

    @computed_field
    @property
    def seconds_since_contact(self) -> int | None:
        if self.last_seen_at is None:
            return None
        return max(0, int((datetime.now(UTC) - self.last_seen_at).total_seconds()))


class DeviceCredential(DeviceOutput):
    token: str


class MonthlyOutput(BaseModel):
    month: date
    sample_count: int
    avg_temp_inside: float
    avg_temp_outside: float
    avg_humidity_inside: float
    avg_humidity_outside: float
    avg_occupancy: float
    ac_on_percent: float
    finalized: bool


def commit(session: Session, conflict: str = "Registro vinculado a outros dados ou já cadastrado"):
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise HTTPException(409, conflict) from None


def get_unit(session: Session, unit_id: str) -> Unit:
    unit = session.get(Unit, unit_id)
    if unit is None:
        raise HTTPException(404, "Unidade não encontrada")
    return unit


def get_room(session: Session, room_id: str) -> Room:
    room = session.get(Room, room_id)
    if room is None:
        raise HTTPException(404, "Sala não encontrada")
    return room


def default_unit(session: Session) -> Unit:
    unit = session.get(Unit, DEFAULT_UNIT_ID)
    if unit is None:
        unit = session.scalar(select(Unit).where(Unit.name == DEFAULT_UNIT_NAME))
    if unit is None:
        unit = Unit(id=DEFAULT_UNIT_ID, name=DEFAULT_UNIT_NAME)
        session.add(unit)
        session.flush()
    return unit


def locate_unit(unit: Unit, climate: ClimateService) -> None:
    """Grava a cidade como "Nome - UF" e as coordenadas usadas para a temperatura externa."""
    if not unit.city:
        unit.latitude = unit.longitude = None
        return
    name, uf = split_city(unit.city)
    try:
        place = climate.locate(name, uf)
    except ClimateUnavailable:
        raise HTTPException(
            503, "Serviço de localização indisponível; tente de novo em instantes"
        ) from None
    if place is None:
        raise HTTPException(422, "Cidade não encontrada")
    found = UF_BY_NAME.get(place.state)
    unit.city = f"{place.name} - {found}" if found else place.name
    unit.latitude, unit.longitude = place.latitude, place.longitude


def create_management_router() -> APIRouter:
    router = APIRouter(dependencies=[Depends(require_user)], tags=["Unidades e salas"])

    def unit_output(unit: Unit, room_count: int) -> UnitOutput:
        return UnitOutput(
            id=unit.id,
            name=unit.name,
            address=unit.address,
            city=unit.city,
            latitude=unit.latitude,
            longitude=unit.longitude,
            room_count=room_count,
        )

    def room_count(session: Session, unit_id: str) -> int:
        return session.scalar(select(func.count()).where(Room.unit_id == unit_id))

    @router.get("/units", response_model=list[UnitOutput])
    def units(session: Db):
        counts = select(Room.unit_id, func.count().label("rooms")).group_by(Room.unit_id).subquery()
        rows = session.execute(
            select(Unit, func.coalesce(counts.c.rooms, 0))
            .outerjoin(counts, counts.c.unit_id == Unit.id)
            .order_by(Unit.name)
        )
        return [unit_output(unit, count) for unit, count in rows]

    @router.post("/units", response_model=UnitOutput, status_code=201, dependencies=Admin)
    def create_unit(payload: UnitInput, session: Db, climate: Climate):
        unit = Unit(id=f"unidade-{uuid4().hex[:16]}", **payload.model_dump())
        locate_unit(unit, climate)
        session.add(unit)
        commit(session, "Já existe uma unidade com este nome")
        return unit_output(unit, 0)

    @router.put("/units/{unit_id}", response_model=UnitOutput, dependencies=Admin)
    def update_unit(unit_id: str, payload: UnitInput, session: Db, climate: Climate):
        unit = get_unit(session, unit_id)
        moved = payload.city != unit.city or (unit.city and unit.latitude is None)
        for field, value in payload.model_dump().items():
            setattr(unit, field, value)
        if moved:
            locate_unit(unit, climate)
        commit(session, "Já existe uma unidade com este nome")
        return unit_output(unit, room_count(session, unit.id))

    @router.delete("/units/{unit_id}", status_code=204, dependencies=Admin)
    def delete_unit(unit_id: str, session: Db):
        unit = get_unit(session, unit_id)
        if room_count(session, unit.id):
            raise HTTPException(409, "Mova ou exclua as salas antes de excluir a unidade")
        session.delete(unit)
        commit(session)
        return Response(status_code=204)

    @router.get("/rooms", response_model=list[RoomOutput])
    def rooms(session: Db, unit_id: Annotated[str | None, Query(max_length=64)] = None):
        counts = (
            select(AirConditioner.room_id, func.count().label("appliances"))
            .group_by(AirConditioner.room_id)
            .subquery()
        )
        query = (
            select(Room, func.coalesce(counts.c.appliances, 0))
            .outerjoin(counts, counts.c.room_id == Room.id)
            .order_by(Room.name, Room.id)
        )
        if unit_id:
            query = query.where(Room.unit_id == unit_id)
        return [
            RoomOutput.model_validate(room).model_copy(update={"appliance_count": count})
            for room, count in session.execute(query)
        ]

    def require_unit(session: Session, unit_id: str):
        if session.get(Unit, unit_id) is None:
            raise HTTPException(422, "Unidade não encontrada")

    @router.post("/rooms", response_model=RoomOutput, status_code=201, dependencies=Admin)
    def create_room(payload: RoomInput, session: Db):
        require_unit(session, payload.unit_id)
        room = Room(id=f"sala-{uuid4().hex[:16]}", **payload.model_dump())
        session.add(room)
        commit(session)
        return room

    @router.put("/rooms/{room_id}", response_model=RoomOutput, dependencies=Admin)
    def update_room(room_id: str, payload: RoomInput, session: Db):
        room = get_room(session, room_id)
        require_unit(session, payload.unit_id)
        for field, value in payload.model_dump().items():
            setattr(room, field, value)
        commit(session)
        return room

    @router.delete("/rooms/{room_id}", status_code=204, dependencies=Admin)
    def delete_room(room_id: str, session: Db):
        session.delete(get_room(session, room_id))
        commit(session)
        return Response(status_code=204)

    @router.get("/rooms/{room_id}/appliances", response_model=list[ApplianceOutput])
    def appliances(room_id: str, session: Db):
        get_room(session, room_id)
        return session.scalars(
            select(AirConditioner)
            .where(AirConditioner.room_id == room_id)
            .order_by(AirConditioner.name)
        ).all()

    @router.post(
        "/rooms/{room_id}/appliances",
        response_model=ApplianceOutput,
        status_code=201,
        dependencies=Admin,
    )
    def create_appliance(room_id: str, payload: ApplianceInput, session: Db):
        get_room(session, room_id)
        appliance = AirConditioner(room_id=room_id, **payload.model_dump())
        resolve_appliance_ir(appliance)
        session.add(appliance)
        commit(session)
        return appliance

    def get_appliance(session: Session, room_id: str, appliance_id: UUID):
        appliance = session.get(AirConditioner, appliance_id)
        if appliance is None or appliance.room_id != room_id:
            raise HTTPException(404, "Aparelho não encontrado nesta sala")
        return appliance

    @router.put(
        "/rooms/{room_id}/appliances/{appliance_id}",
        response_model=ApplianceOutput,
        dependencies=Admin,
    )
    def update_appliance(room_id: str, appliance_id: UUID, payload: ApplianceInput, session: Db):
        appliance = get_appliance(session, room_id, appliance_id)
        for field, value in payload.model_dump().items():
            setattr(appliance, field, value)
        resolve_appliance_ir(appliance)
        commit(session)
        return appliance

    @router.delete(
        "/rooms/{room_id}/appliances/{appliance_id}", status_code=204, dependencies=Admin
    )
    def delete_appliance(room_id: str, appliance_id: UUID, session: Db):
        session.delete(get_appliance(session, room_id, appliance_id))
        commit(session)
        return Response(status_code=204)

    @router.get("/rooms/{room_id}/devices", response_model=list[DeviceOutput])
    def devices(room_id: str, session: Db):
        get_room(session, room_id)
        return session.scalars(select(Device).where(Device.room_id == room_id)).all()

    @router.post(
        "/rooms/{room_id}/devices",
        response_model=DeviceCredential,
        status_code=201,
        dependencies=Admin,
    )
    def provision_device(room_id: str, session: Db):
        get_room(session, room_id)
        token = secrets.token_urlsafe(32)
        device = Device(
            id=f"esp32-{uuid4().hex[:16]}", room_id=room_id, token_hash=hash_device_token(token)
        )
        session.add(device)
        commit(session)
        return DeviceCredential(id=device.id, room_id=room_id, enabled=device.enabled, token=token)

    @router.post(
        "/rooms/{room_id}/devices/{device_id}/token",
        response_model=DeviceCredential,
        dependencies=Admin,
    )
    def regenerate_device_token(room_id: str, device_id: str, session: Db):
        get_room(session, room_id)
        device = session.get(Device, device_id)
        if device is None or device.room_id != room_id:
            raise HTTPException(404, "Dispositivo não encontrado nesta sala")
        token = secrets.token_urlsafe(32)
        device.token_hash = hash_device_token(token)
        commit(session)
        return DeviceCredential(id=device.id, room_id=room_id, enabled=device.enabled, token=token)

    @router.get("/rooms/{room_id}/monthly", response_model=list[MonthlyOutput])
    def monthly(room_id: str, session: Db):
        get_room(session, room_id)
        return monthly_history(session, room_id)

    return router
