"""Reenvio do protocolo cadastrado ao ESP32 da sala, sem alterar o comando do ar."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, update

from app.dependencies import AdminUser, Db
from app.ir_protocols import device_protocols
from app.management import get_room
from app.models import AirConditioner, Device, Room


class ProtocolDispatch(BaseModel):
    revision: int
    protocols: str
    pending: int
    candidates: int
    message: str


def create_ir_control_router() -> APIRouter:
    router = APIRouter(tags=["Protocolo infravermelho"])

    @router.post("/rooms/{room_id}/ir-protocol", response_model=ProtocolDispatch)
    def send_protocol(room_id: str, session: Db, principal: AdminUser):
        room = get_room(session, room_id)
        device = session.scalar(select(Device).where(Device.room_id == room.id, Device.enabled))
        if device is None:
            raise HTTPException(
                409, "Cadastre um ESP32 ativo nesta sala antes de enviar o protocolo"
            )
        appliances = session.scalars(
            select(AirConditioner).where(
                AirConditioner.room_id == room.id, AirConditioner.status == "ativo"
            )
        ).all()
        protocols = device_protocols(appliances)
        if not protocols:
            raise HTTPException(
                409, "Informe o protocolo no cadastro de um aparelho ativo desta sala"
            )
        revision = session.scalar(
            update(Room)
            .where(Room.id == room.id)
            .values(ir_revision=Room.ir_revision + 1)
            .returning(Room.ir_revision)
        )
        session.commit()
        return ProtocolDispatch(
            revision=revision,
            protocols=protocols,
            pending=sum(not item.ir_protocol for item in appliances),
            candidates=sum(item.ir_source.endswith("_candidate") for item in appliances),
            message="Protocolo preparado. O ESP32 receberá no próximo contato com o site.",
        )

    return router
