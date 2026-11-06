import logging
from typing import Annotated, Protocol
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import AwareDatetime, BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.dependencies import Db, require_user
from app.models import Alert, SensorReading
from app.repository import room_exists

COMFORT_MAX_TEMP_C = 28.0
HUMIDITY_MAX_PERCENT = 70.0

logger = logging.getLogger("movement.alerts")


class TelemetryObserver(Protocol):
    def on_reading(self, session: Session, reading: SensorReading) -> None: ...


class TelemetrySubject:
    def __init__(self) -> None:
        self._observers: list[TelemetryObserver] = []

    def attach(self, observer: TelemetryObserver) -> None:
        self._observers.append(observer)

    def notify(self, session: Session, reading: SensorReading) -> None:
        for observer in self._observers:
            observer.on_reading(session, reading)


def record_alert(
    session: Session, reading: SensorReading, kind: str, message: str, value: float
) -> None:
    session.add(Alert(room_id=reading.room_id, kind=kind, message=message, value=value))
    logger.warning("%s: %s", reading.room_id, message)


class ComfortAlertObserver:
    """Sala ocupada com temperatura interna acima do limite de conforto."""

    def on_reading(self, session: Session, reading: SensorReading) -> None:
        if reading.occupancy > 0 and reading.temp_inside > COMFORT_MAX_TEMP_C:
            message = (
                f"Sala ocupada a {reading.temp_inside:.1f} °C (limite {COMFORT_MAX_TEMP_C:.0f} °C)"
            ).replace(".", ",")
            record_alert(session, reading, "conforto", message, reading.temp_inside)


class HumidityAlertObserver:
    """Umidade interna acima do limite."""

    def on_reading(self, session: Session, reading: SensorReading) -> None:
        if reading.humidity_inside > HUMIDITY_MAX_PERCENT:
            message = (
                f"Umidade interna em {reading.humidity_inside:.0f}% "
                f"(limite {HUMIDITY_MAX_PERCENT:.0f}%)"
            )
            record_alert(session, reading, "umidade", message, reading.humidity_inside)


def default_subject() -> TelemetrySubject:
    subject = TelemetrySubject()
    subject.attach(ComfortAlertObserver())
    subject.attach(HumidityAlertObserver())
    return subject


class AlertOutput(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    kind: str
    message: str
    value: float
    created_at: AwareDatetime


def create_alerts_router() -> APIRouter:
    router = APIRouter(dependencies=[Depends(require_user)], tags=["Alertas"])

    @router.get("/rooms/{room_id}/alerts", response_model=list[AlertOutput])
    def alerts(room_id: str, session: Db, limit: Annotated[int, Query(ge=1, le=100)] = 20):
        if not room_exists(session, room_id):
            raise HTTPException(404, "Ambiente não encontrado")
        return session.scalars(
            select(Alert)
            .where(Alert.room_id == room_id)
            .order_by(Alert.created_at.desc(), Alert.id.desc())
            .limit(limit)
        ).all()

    return router
