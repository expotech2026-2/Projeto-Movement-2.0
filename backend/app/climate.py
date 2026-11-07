"""Temperatura externa: Open-Meteo (grátis, sem chave) e OpenWeatherMap como reserva."""

import time
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

import httpx

GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
OPENWEATHER_URL = "https://api.openweathermap.org/data/2.5/weather"
PREFERRED_STATE = "São Paulo"
CACHE_SECONDS = 900  # a Open-Meteo atualiza as condições atuais a cada 15 min
TIMEOUT_SECONDS = 5.0
# Nomes iguais aos do IBGE e ao campo admin1 da Open-Meteo.
UF_NAMES = {
    "AC": "Acre",
    "AL": "Alagoas",
    "AP": "Amapá",
    "AM": "Amazonas",
    "BA": "Bahia",
    "CE": "Ceará",
    "DF": "Distrito Federal",
    "ES": "Espírito Santo",
    "GO": "Goiás",
    "MA": "Maranhão",
    "MT": "Mato Grosso",
    "MS": "Mato Grosso do Sul",
    "MG": "Minas Gerais",
    "PA": "Pará",
    "PB": "Paraíba",
    "PR": "Paraná",
    "PE": "Pernambuco",
    "PI": "Piauí",
    "RJ": "Rio de Janeiro",
    "RN": "Rio Grande do Norte",
    "RS": "Rio Grande do Sul",
    "RO": "Rondônia",
    "RR": "Roraima",
    "SC": "Santa Catarina",
    "SP": "São Paulo",
    "SE": "Sergipe",
    "TO": "Tocantins",
}
UF_BY_NAME = {name: uf for uf, name in UF_NAMES.items()}


class ClimateUnavailable(Exception):
    pass


def split_city(text: str) -> tuple[str, str | None]:
    """'Campinas - SP' vira ('Campinas', 'SP'); sem uma UF válida no fim, a UF é None."""
    name, separator, uf = text.rpartition(" - ")
    uf = uf.strip().upper()
    if separator and name.strip() and uf in UF_NAMES:
        return name.strip(), uf
    return text.strip(), None


@dataclass(frozen=True)
class Place:
    name: str
    state: str
    latitude: float
    longitude: float


@dataclass(frozen=True)
class Outside:
    temperature: float
    humidity: float
    source: str


class ClimateService(Protocol):
    def locate(self, city: str, uf: str | None = None) -> Place | None: ...

    def outside(self, latitude: float, longitude: float) -> Outside | None: ...


class WeatherSource(Protocol):
    def current(self, latitude: float, longitude: float, timeout: float) -> Outside: ...


class OpenMeteoWeather:
    def current(self, latitude: float, longitude: float, timeout: float) -> Outside:
        response = httpx.get(
            FORECAST_URL,
            params={
                "latitude": latitude,
                "longitude": longitude,
                "current": "temperature_2m,relative_humidity_2m",
            },
            timeout=timeout,
        )
        response.raise_for_status()
        current = response.json()["current"]
        return Outside(
            float(current["temperature_2m"]), float(current["relative_humidity_2m"]), "Open-Meteo"
        )


class OpenWeatherMapWeather:
    """Reserva do clima atual; precisa da chave em MOVEMENT_OPENWEATHER_API_KEY."""

    def __init__(self, api_key: str) -> None:
        self.api_key = api_key

    def current(self, latitude: float, longitude: float, timeout: float) -> Outside:
        response = httpx.get(
            OPENWEATHER_URL,
            params={"lat": latitude, "lon": longitude, "units": "metric", "appid": self.api_key},
            timeout=timeout,
        )
        response.raise_for_status()
        main = response.json()["main"]
        return Outside(float(main["temp"]), float(main["humidity"]), "OpenWeatherMap")


class OpenMeteoClimate:
    """Cidade pelo buscador da Open-Meteo; clima pela Open-Meteo e, se falhar, pelas reservas."""

    def __init__(
        self, timeout: float = TIMEOUT_SECONDS, backups: Sequence[WeatherSource] = ()
    ) -> None:
        self.timeout = timeout
        self.sources: list[WeatherSource] = [OpenMeteoWeather(), *backups]
        self._cache: dict[tuple[float, float], tuple[float, Outside]] = {}

    def locate(self, city: str, uf: str | None = None) -> Place | None:
        """Coordenadas da cidade no Brasil: só na UF informada ou, sem UF, preferindo SP."""
        try:
            response = httpx.get(
                GEOCODING_URL,
                params={"name": city, "count": 10, "language": "pt", "countryCode": "BR"},
                timeout=self.timeout,
            )
            response.raise_for_status()
            results = response.json().get("results") or []
        except (httpx.HTTPError, ValueError) as error:
            raise ClimateUnavailable from error
        if uf:
            results = [item for item in results if item.get("admin1") == UF_NAMES[uf]]
        if not results:
            return None
        best = next((item for item in results if item.get("admin1") == PREFERRED_STATE), results[0])
        return Place(best["name"], best.get("admin1", ""), best["latitude"], best["longitude"])

    def outside(self, latitude: float, longitude: float) -> Outside | None:
        """Clima atual guardado por 15 min; se todas as fontes falharem, repete o último."""
        key = (round(latitude, 3), round(longitude, 3))
        cached = self._cache.get(key)
        now = time.monotonic()
        if cached and now - cached[0] < CACHE_SECONDS:
            return cached[1]
        for source in self.sources:
            try:
                value = source.current(latitude, longitude, self.timeout)
            except (httpx.HTTPError, KeyError, TypeError, ValueError):
                continue
            self._cache[key] = (now, value)
            return value
        return cached[1] if cached else None
