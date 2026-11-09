"""Último contato e diagnóstico do ESP32, lidos dos cabeçalhos de cada chamada dele à API."""

from datetime import datetime, timedelta

from fastapi import Request

from app.models import Device

# O ESP32 busca o comando do site pelo menos a cada 60 s; 150 s tolera uma consulta perdida.
OFFLINE_AFTER = timedelta(seconds=150)
WRITE_EVERY = timedelta(seconds=10)
TEXT_HEADERS = {
    "firmware": ("x-movement-firmware", 32),
    "sensor_faults": ("x-movement-sensors", 120),
    "ac_state": ("x-movement-ac", 60),
}
NUMBER_HEADERS = {
    "rssi": ("x-movement-rssi", -127, 0),
    "uptime_seconds": ("x-movement-uptime", 0, 10**10),
}


def diagnostics(request: Request) -> dict[str, str | int]:
    """Campos de diagnóstico válidos dos cabeçalhos; os ausentes ou inválidos ficam de fora."""
    values: dict[str, str | int] = {}
    for field, (header, size) in TEXT_HEADERS.items():
        raw = request.headers.get(header)
        if raw is not None:
            values[field] = raw.strip()[:size]
    for field, (header, low, high) in NUMBER_HEADERS.items():
        try:
            number = int(request.headers.get(header, ""))
        except ValueError:
            continue
        if low <= number <= high:
            values[field] = number
    return values


def record_contact(device: Device, request: Request, now: datetime) -> bool:
    """Atualiza o contato e o diagnóstico; devolve True quando há algo novo para gravar."""
    values = diagnostics(request)
    changed = any(getattr(device, field) != value for field, value in values.items())
    stale = device.last_seen_at is None or now - device.last_seen_at >= WRITE_EVERY
    if not (changed or stale):
        return False
    for field, value in values.items():
        setattr(device, field, value)
    device.last_seen_at = now
    return True


def is_online(last_seen_at: datetime | None, now: datetime) -> bool:
    return last_seen_at is not None and now - last_seen_at < OFFLINE_AFTER
