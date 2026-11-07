"""Municípios do Brasil, buscados na API de localidades do IBGE (sem cópia no código)."""

import time
from typing import Annotated, Protocol

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from app.dependencies import require_user

IBGE_URL = "https://servicodados.ibge.gov.br/api/v1/localidades/municipios"
CACHE_SECONDS = 24 * 3600  # a lista de municípios quase nunca muda
TIMEOUT_SECONDS = 15.0


class CitiesUnavailable(Exception):
    pass


class City(BaseModel):
    id: int
    name: str
    state: str


class CitySource(Protocol):
    def cities(self) -> list[City]: ...


class IbgeCities:
    def __init__(self, timeout: float = TIMEOUT_SECONDS) -> None:
        self.timeout = timeout
        self._cache: list[City] = []
        self._loaded_at = 0.0

    def cities(self) -> list[City]:
        """Lista em ordem alfabética, guardada por 24 h; repete a última se o IBGE falhar."""
        now = time.monotonic()
        if self._cache and now - self._loaded_at < CACHE_SECONDS:
            return self._cache
        try:
            response = httpx.get(
                IBGE_URL, params={"view": "nivelado", "orderBy": "nome"}, timeout=self.timeout
            )
            response.raise_for_status()
            loaded = [
                City(id=item["municipio-id"], name=item["municipio-nome"], state=item["UF-sigla"])
                for item in response.json()
            ]
        except (httpx.HTTPError, ValueError, KeyError, TypeError) as error:
            if self._cache:
                return self._cache
            raise CitiesUnavailable from error
        self._cache, self._loaded_at = loaded, now
        return loaded


def city_source(request: Request) -> CitySource:
    return request.app.state.cities


Cities = Annotated[CitySource, Depends(city_source)]


def create_cities_router() -> APIRouter:
    router = APIRouter(tags=["Cidades"])

    @router.get("/cities", response_model=list[City], dependencies=[Depends(require_user)])
    def cities(source: Cities):
        try:
            return source.cities()
        except CitiesUnavailable:
            raise HTTPException(
                503, "Lista de municípios indisponível; digite o nome da cidade"
            ) from None

    return router
