from datetime import date, datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Computed,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


DEFAULT_UNIT_ID = "unidade-principal"
DEFAULT_UNIT_NAME = "Unidade principal"


class Unit(Base):
    __tablename__ = "units"
    __table_args__ = (UniqueConstraint("name", name="uq_units_name"),)
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    address: Mapped[str] = mapped_column(String(160), default="", server_default="")


class Room(Base):
    __tablename__ = "rooms"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    unit_id: Mapped[str] = mapped_column(ForeignKey("units.id"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    location: Mapped[str] = mapped_column(String(120), default="", server_default="")
    capacity: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    __table_args__ = (CheckConstraint("capacity BETWEEN 1 AND 10000", name="ck_room_capacity"),)


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        UniqueConstraint("username", name="uq_users_username"),
        CheckConstraint("role IN ('admin', 'professor')", name="ck_user_role"),
    )
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    username: Mapped[str] = mapped_column(String(60))
    full_name: Mapped[str] = mapped_column(String(120))
    role: Mapped[str] = mapped_column(String(20))
    password_hash: Mapped[str] = mapped_column(String(200))
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    session_version: Mapped[int] = mapped_column(Integer, server_default="0")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class CatalogModel(Base):
    __tablename__ = "ac_catalog"
    # Modelos da tabela PBE do Inmetro; recarregados por "movement catalog-import".
    __table_args__ = (Index("ix_ac_catalog_brand_kind", "brand", "kind"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    brand: Mapped[str] = mapped_column(String(80))
    model: Mapped[str] = mapped_column(String(120))
    kind: Mapped[str] = mapped_column(String(20))
    indoor_unit: Mapped[str] = mapped_column(String(80))
    outdoor_unit: Mapped[str] = mapped_column(String(80))
    function: Mapped[str] = mapped_column(String(20))
    voltage: Mapped[str] = mapped_column(String(40))
    inverter: Mapped[bool] = mapped_column(Boolean)
    refrigerant: Mapped[str] = mapped_column(String(20))
    capacity_btu: Mapped[int] = mapped_column(Integer)
    idrs: Mapped[float | None] = mapped_column(Float)
    annual_kwh: Mapped[float | None] = mapped_column(Float)
    energy_class: Mapped[str] = mapped_column(String(2))
    registration: Mapped[str] = mapped_column(String(20))
    corrected: Mapped[bool] = mapped_column(Boolean, default=False)


class AirConditioner(Base):
    __tablename__ = "air_conditioners"
    __table_args__ = (
        CheckConstraint("capacity_btu BETWEEN 1000 AND 500000", name="ck_ac_capacity"),
        CheckConstraint(
            "kind IN ('split', 'janela', 'cassete', 'piso_teto', 'portatil', 'vrf')",
            name="ck_ac_kind",
        ),
        CheckConstraint("status IN ('ativo', 'manutencao', 'inativo')", name="ck_ac_status"),
    )
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    room_id: Mapped[str] = mapped_column(ForeignKey("rooms.id"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    kind: Mapped[str] = mapped_column(String(20))
    brand: Mapped[str] = mapped_column(String(80), default="")
    model: Mapped[str] = mapped_column(String(80), default="")
    capacity_btu: Mapped[int] = mapped_column(Integer)
    inverter: Mapped[bool] = mapped_column(Boolean, default=False)
    status: Mapped[str] = mapped_column(String(20), default="ativo")


class MonthlySummary(Base):
    __tablename__ = "monthly_summaries"
    __table_args__ = (CheckConstraint("sample_count > 0", name="ck_summary_count"),)
    room_id: Mapped[str] = mapped_column(ForeignKey("rooms.id"), primary_key=True)
    month: Mapped[date] = mapped_column(Date, primary_key=True)
    sample_count: Mapped[int] = mapped_column(BigInteger)
    temp_inside_sum: Mapped[float] = mapped_column(Float)
    temp_outside_sum: Mapped[float] = mapped_column(Float)
    humidity_inside_sum: Mapped[float] = mapped_column(Float)
    humidity_outside_sum: Mapped[float] = mapped_column(Float)
    occupancy_sum: Mapped[float] = mapped_column(Float)
    ac_on_sum: Mapped[float] = mapped_column(Float)
    avg_temp_inside: Mapped[float] = mapped_column(
        Float, Computed("temp_inside_sum / sample_count", persisted=True)
    )
    avg_temp_outside: Mapped[float] = mapped_column(
        Float, Computed("temp_outside_sum / sample_count", persisted=True)
    )
    avg_humidity_inside: Mapped[float] = mapped_column(
        Float, Computed("humidity_inside_sum / sample_count", persisted=True)
    )
    avg_humidity_outside: Mapped[float] = mapped_column(
        Float, Computed("humidity_outside_sum / sample_count", persisted=True)
    )
    avg_occupancy: Mapped[float] = mapped_column(
        Float, Computed("occupancy_sum / sample_count", persisted=True)
    )
    ac_on_percent: Mapped[float] = mapped_column(
        Float, Computed("100.0 * ac_on_sum / sample_count", persisted=True)
    )


class Device(Base):
    __tablename__ = "devices"
    # Um dispositivo ativo por ambiente nesta primeira entrega.
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    room_id: Mapped[str] = mapped_column(ForeignKey("rooms.id"), unique=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)


class SensorReading(Base):
    __tablename__ = "sensor_readings"
    __table_args__ = (
        UniqueConstraint("device_id", "message_id", name="uq_reading_device_message"),
        Index("ix_readings_room_measured", "room_id", "measured_at"),
        Index("ix_readings_measured", "measured_at"),
        CheckConstraint("occupancy >= 0", name="ck_reading_occupancy"),
        CheckConstraint("temp_inside BETWEEN -40 AND 85", name="ck_reading_temp_inside"),
        CheckConstraint("temp_outside BETWEEN -40 AND 85", name="ck_reading_temp_outside"),
        CheckConstraint("humidity_inside BETWEEN 0 AND 100", name="ck_reading_humidity_inside"),
        CheckConstraint("humidity_outside BETWEEN 0 AND 100", name="ck_reading_humidity_outside"),
        CheckConstraint(
            "target_temp = 0 OR target_temp BETWEEN 16 AND 30", name="ck_reading_target"
        ),
    )
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    message_id: Mapped[UUID] = mapped_column(Uuid)
    device_id: Mapped[str] = mapped_column(ForeignKey("devices.id"))
    room_id: Mapped[str] = mapped_column(ForeignKey("rooms.id"))
    measured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    occupancy: Mapped[int] = mapped_column(Integer)
    temp_inside: Mapped[float] = mapped_column(Float)
    temp_outside: Mapped[float] = mapped_column(Float)
    target_temp: Mapped[float] = mapped_column(Float)
    humidity_inside: Mapped[float] = mapped_column(Float)
    humidity_outside: Mapped[float] = mapped_column(Float)
    ac_on: Mapped[bool] = mapped_column(Boolean)
    manual_mode: Mapped[bool] = mapped_column(Boolean)
