"""Associações por modelo, com fonte e grau de evidência; sem o modelo, um candidato pela marca."""

import json
import re
from pathlib import Path

DATA = Path(__file__).with_name("data") / "ir_protocols.json"
# Protocolo mais comum da marca no Brasil (IRremoteESP8266 v2.9.0); precisa de IR_TESTE no aparelho.
BRAND_PROTOCOLS = {
    "LG": ("LG2", 2),
    "GREE": ("GREE", 1),
    "SAMSUNG": ("SAMSUNG_AC", 1),
    "MIDEA": ("COOLIX", 1),
    "SPRINGER": ("COOLIX", 1),
    "SPRINGERMIDEA": ("COOLIX", 1),
    "CARRIER": ("COOLIX", 1),
    "TCL": ("TCL112AC", 1),
    "DAIKIN": ("DAIKIN", 1),
    "FUJITSU": ("FUJITSU_AC", 1),
    "FUJITSUAIRSTAGE": ("FUJITSU_AC", 1),
    "AIRSTAGE": ("FUJITSU_AC", 1),
    "HITACHI": ("HITACHI_AC", 1),
    "CONSUL": ("WHIRLPOOL_AC", 1),
    "BRASTEMP": ("WHIRLPOOL_AC", 1),
}


def normalize(value: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", value.upper())


def lookup(brand: str, model: str) -> dict | None:
    key = normalize(brand), normalize(model)
    return next(
        (
            row
            for row in json.loads(DATA.read_text(encoding="utf-8"))
            if (normalize(row["brand"]), normalize(row["model"])) == key
        ),
        None,
    )


def brand_candidate(brand: str) -> dict | None:
    match = BRAND_PROTOCOLS.get(normalize(brand))
    if match is None:
        return None
    return {"protocol": match[0], "ir_model": match[1], "confidence": "brand_candidate"}


def device_protocols(appliances: list) -> str:
    """Uma configuração plana para o parser do ESP; só os aparelhos ativos e resolvidos."""
    pairs = {
        (item.ir_protocol, item.ir_model)
        for item in appliances
        if item.status == "ativo" and item.ir_protocol
    }
    return ",".join(f"{protocol}:{model}" for protocol, model in sorted(pairs))
