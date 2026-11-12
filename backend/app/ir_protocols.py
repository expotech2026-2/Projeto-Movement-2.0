"""Associações por modelo, com fonte e grau de evidência; marca sozinha não confirma IR."""

import json
import re
from pathlib import Path

DATA = Path(__file__).with_name("data") / "ir_protocols.json"


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


def device_protocols(appliances: list) -> str:
    """Uma configuração plana para o parser do ESP; só os aparelhos ativos e resolvidos."""
    pairs = {
        (item.ir_protocol, item.ir_model)
        for item in appliances
        if item.status == "ativo" and item.ir_protocol
    }
    return ",".join(f"{protocol}:{model}" for protocol, model in sorted(pairs))
