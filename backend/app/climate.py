"""Temperatura externa: Open-Meteo (grátis, sem chave) e OpenWeatherMap como reserva."""

import threading
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Protocol

import httpx

GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
OPENWEATHER_URL = "https://api.openweathermap.org/data/2.5/weather"
PREFERRED_STATE = "São Paulo"
CACHE_SECONDS = 900  # a Open-Meteo atualiza as condições atuais a cada 15 min
RETRY_SECONDS = 60  # com todas as fontes fora do ar, só tenta de novo depois deste tempo
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

    def outside_cached(self, latitude: float, longitude: float) -> Outside | None: ...


def run_in_background(task: Callable[[], None]) -> None:
    threading.Thread(target=task, daemon=True).start()


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
        self,
        timeout: float = TIMEOUT_SECONDS,
        backups: Sequence[WeatherSource] = (),
        background: Callable[[Callable[[], None]], None] = run_in_background,
    ) -> None:
        self.timeout = timeout
        self.sources: list[WeatherSource] = [OpenMeteoWeather(), *backups]
        self.background = background
        self._cache: dict[tuple[float, float], tuple[float, Outside]] = {}
        self._failed: dict[tuple[float, float], float] = {}
        self._refreshing: set[tuple[float, float]] = set()
        self._lock = threading.Lock()

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

    def _needs_fetch(self, key: tuple[float, float]) -> bool:
        """Falso com valor de menos de 15 min ou com uma falha de menos de 1 min."""
        now = time.monotonic()
        cached, failed = self._cache.get(key), self._failed.get(key)
        if cached and now - cached[0] < CACHE_SECONDS:
            return False
        return failed is None or now - failed >= RETRY_SECONDS

    def _fetch(self, key: tuple[float, float], latitude: float, longitude: float) -> None:
        for source in self.sources:
            try:
                value = source.current(latitude, longitude, self.timeout)
            except (httpx.HTTPError, KeyError, TypeError, ValueError):
                continue
            self._cache[key] = (time.monotonic(), value)
            self._failed.pop(key, None)
            return
        self._failed[key] = time.monotonic()

    def _last(self, key: tuple[float, float]) -> Outside | None:
        cached = self._cache.get(key)
        return cached[1] if cached else None

    def outside(self, latitude: float, longitude: float) -> Outside | None:
        """Clima atual guardado por 15 min; se todas as fontes falharem, repete o último."""
        key = (round(latitude, 3), round(longitude, 3))
        if self._needs_fetch(key):
            self._fetch(key, latitude, longitude)
        return self._last(key)

    def outside_cached(self, latitude: float, longitude: float) -> Outside | None:
        """Para o ESP32, que desiste em 5 s: responde com o que já tem e atualiza por fora."""
        key = (round(latitude, 3), round(longitude, 3))
        with self._lock:
            start = self._needs_fetch(key) and key not in self._refreshing
            if start:
                self._refreshing.add(key)
        if start:

            def refresh() -> None:
                try:
                    self._fetch(key, latitude, longitude)
                finally:
                    self._refreshing.discard(key)

            self.background(refresh)
        return self._last(key)
