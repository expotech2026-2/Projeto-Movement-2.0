"""Números da sala que o ESP32 usa para escolher o ajuste do ar (docs/fisica.md, seção 8)."""

import math
from dataclasses import dataclass

from app.management import AREA_PER_PERSON_M2, room_volume

U_WALL = 2.5  # W/(m²·K): alvenaria, valor típico
U_GLASS = 5.8  # W/(m²·K): vidro simples, valor típico
WINDOW_SHARE = 0.25  # da parede externa
SUN_W_M2 = 300 * 0.85  # sol da tarde que atravessa o vidro
LIGHT_W_M2 = 10.0
AIR_CHANGES_PER_HOUR = 1.0  # porta e frestas
AIR_HEAT_CAPACITY = 1.2 * 1005  # J/(m³·K)
SENSIBLE_SHARE = 0.75  # parte da capacidade nominal que baixa a temperatura
BTU_H_PER_W = 3.412


@dataclass(frozen=True)
class RoomThermal:
    ua_w_k: float
    fixed_heat_w: float
    ac_power_w: float


def room_thermal(
    area_m2: float | None, ceiling_height_m: float, capacity: int, active_btu: int
) -> RoomThermal:
    """Estimativa pelo cadastro: uma parede externa (lado de uma sala quadrada) com 25% de vidro."""
    area = area_m2 or capacity * AREA_PER_PERSON_M2
    wall = math.sqrt(area) * ceiling_height_m
    window = WINDOW_SHARE * wall
    air = AIR_CHANGES_PER_HOUR * room_volume(area_m2, ceiling_height_m, capacity) / 3600
    ua = (wall - window) * U_WALL + window * U_GLASS + air * AIR_HEAT_CAPACITY
    return RoomThermal(
        ua_w_k=round(ua, 1),
        fixed_heat_w=round(area * LIGHT_W_M2 + window * SUN_W_M2, 1),
        ac_power_w=round(active_btu * SENSIBLE_SHARE / BTU_H_PER_W, 1),
    )
