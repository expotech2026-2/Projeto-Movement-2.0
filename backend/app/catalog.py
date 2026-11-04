"""Catálogo de condicionadores de ar registrados no Programa Brasileiro de Etiquetagem."""

import csv
import json
from pathlib import Path
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy import delete, func, insert, select
from sqlalchemy.orm import Session

from app.dependencies import Db, require_user
from app.models import CatalogModel

DATA = Path(__file__).resolve().parent / "data"
CATALOG_CSV = DATA / "inmetro_condicionadores.csv"
CATALOG_META = DATA / "inmetro_condicionadores.json"
CATALOG_KINDS = ("split", "cassete", "piso_teto", "janela")


def read_catalog(path: Path = CATALOG_CSV) -> list[dict]:
    with path.open(encoding="utf-8", newline="") as source:
        rows = []
        for line, row in enumerate(csv.DictReader(source), start=2):
            if row["kind"] not in CATALOG_KINDS or row["function"] not in ("frio", "quente_frio"):
                raise ValueError(f"Linha {line}: tipo ou função desconhecidos")
            capacity = int(row["capacity_btu"])
            if not 1000 <= capacity <= 500000:
                raise ValueError(f"Linha {line}: capacidade fora da faixa permitida")
            rows.append(
                {
                    **{key: row[key].strip() for key in row if key != "corrected"},
                    "inverter": row["inverter"] == "1",
                    "capacity_btu": capacity,
                    "idrs": float(row["idrs"]) if row["idrs"] else None,
                    "annual_kwh": float(row["annual_kwh"]) if row["annual_kwh"] else None,
                    "corrected": row["corrected"] == "1",
                }
            )
    if not rows:
        raise ValueError("Catálogo vazio")
    return rows


def catalog_metadata(path: Path = CATALOG_META) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def replace_catalog(session: Session, rows: list[dict]) -> int:
    session.execute(delete(CatalogModel))
    session.execute(insert(CatalogModel), rows)
    session.commit()
    return len(rows)


class CatalogInfo(BaseModel):
    source: str
    updated_at: str | None
    models: int
    brands: int


class BrandOutput(BaseModel):
    brand: str
    models: int


class CatalogOutput(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    brand: str
    model: str
    kind: str
    indoor_unit: str
    outdoor_unit: str
    function: str
    voltage: str
    inverter: bool
    refrigerant: str
    capacity_btu: int
    idrs: float | None
    annual_kwh: float | None
    energy_class: str
    registration: str
    corrected: bool


def create_catalog_router() -> APIRouter:
    router = APIRouter(
        prefix="/catalog", dependencies=[Depends(require_user)], tags=["Catálogo Inmetro"]
    )

    @router.get("", response_model=CatalogInfo)
    def info(session: Db):
        metadata = catalog_metadata()
        models = session.scalar(select(func.count()).select_from(CatalogModel))
        brands = session.scalar(select(func.count(func.distinct(CatalogModel.brand))))
        return CatalogInfo(
            source=metadata["source"],
            updated_at=metadata.get("updated_at"),
            models=models,
            brands=brands,
        )

    @router.get("/brands", response_model=list[BrandOutput])
    def brands(session: Db):
        rows = session.execute(
            select(CatalogModel.brand, func.count())
            .group_by(CatalogModel.brand)
            .order_by(CatalogModel.brand)
        )
        return [BrandOutput(brand=brand, models=count) for brand, count in rows]

    @router.get("/models", response_model=list[CatalogOutput])
    def models(
        session: Db,
        brand: Annotated[str | None, Query(max_length=80)] = None,
        kind: Literal["split", "cassete", "piso_teto", "janela"] | None = None,
        q: Annotated[str | None, Query(max_length=80)] = None,
        limit: Annotated[int, Query(ge=1, le=2000)] = 500,
    ):
        query = select(CatalogModel)
        if brand:
            query = query.where(CatalogModel.brand == brand.strip().upper())
        if kind:
            query = query.where(CatalogModel.kind == kind)
        if q:
            pattern = f"%{q.strip()}%"
            query = query.where(
                CatalogModel.model.ilike(pattern) | CatalogModel.indoor_unit.ilike(pattern)
            )
        return session.scalars(
            query.order_by(CatalogModel.capacity_btu, CatalogModel.model).limit(limit)
        ).all()

    return router
