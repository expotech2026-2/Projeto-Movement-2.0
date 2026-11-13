"""Escolha do emissor; somente o ESP32 acessa o gateway na rede da sala."""

from ipaddress import IPv4Address, IPv4Network
from typing import Literal
from urllib.parse import urlsplit

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import update

from app.dependencies import AdminUser, Db, require_user
from app.management import get_room
from app.models import Room

Transport = Literal["esp32", "xiaomi"]
LOCAL_NETWORKS = tuple(
    IPv4Network(value) for value in ("10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16")
)


def validate_gateway_url(value: str) -> str:
    try:
        url = urlsplit(value)
        address = IPv4Address(url.hostname or "")
        valid = (
            url.scheme == "http"
            and any(address in network for network in LOCAL_NETWORKS)
            and url.port is not None
            and 1024 <= url.port <= 65535
            and url.path == "/ac"
            and not (url.username or url.password or url.query or url.fragment)
            and value == f"http://{address}:{url.port}/ac"
        )
    except ValueError:
        valid = False
    if not valid:
        raise ValueError("Use o IPv4 local do Xiaomi, por exemplo http://192.168.1.150:8080/ac")
    return value


class TransportInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    transport: Transport
    gateway_url: str = Field(default="", max_length=100)

    @model_validator(mode="after")
    def gateway_for_xiaomi(self) -> "TransportInput":
        if self.transport == "xiaomi":
            self.gateway_url = validate_gateway_url(self.gateway_url)
        else:
            self.gateway_url = ""
        return self


class TransportOutput(BaseModel):
    transport: Transport
    gateway_url: str
    revision: int


def transport_output(room: Room) -> TransportOutput:
    return TransportOutput(
        transport=room.ir_transport,
        gateway_url=room.ir_gateway_url,
        revision=room.ir_transport_revision,
    )


def create_ir_transport_router() -> APIRouter:
    router = APIRouter(tags=["Emissor infravermelho"])

    @router.get(
        "/rooms/{room_id}/ir-transport",
        response_model=TransportOutput,
        dependencies=[Depends(require_user)],
    )
    def get_transport(room_id: str, session: Db):
        return transport_output(get_room(session, room_id))

    @router.put("/rooms/{room_id}/ir-transport", response_model=TransportOutput)
    def set_transport(room_id: str, payload: TransportInput, session: Db, principal: AdminUser):
        room = get_room(session, room_id)
        session.execute(
            update(Room)
            .where(Room.id == room.id)
            .values(
                ir_transport=payload.transport,
                ir_gateway_url=payload.gateway_url,
                ir_transport_revision=Room.ir_transport_revision + 1,
            )
        )
        session.commit()
        session.refresh(room)
        return transport_output(room)

    return router
