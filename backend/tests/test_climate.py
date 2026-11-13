import secrets

import httpx

from app import climate as module
from app.climate import OpenMeteoClimate, OpenWeatherMapWeather, Outside
from app.main import create_app
from app.security import hash_password
from app.settings import Settings

OPEN_METEO = {"current": {"temperature_2m": 27.4, "relative_humidity_2m": 61}}
OPENWEATHER = {"main": {"temp": 26.1, "humidity": 64}}


def answer(url, status=200, payload=None):
    return httpx.Response(status, json=payload or {}, request=httpx.Request("GET", url))


class FakeApis:
    """Responde como as duas APIs; `down` lista as que estão fora do ar."""

    def __init__(self, down=()):
        self.down = set(down)
        self.calls = []

    def __call__(self, url, params, timeout):
        self.calls.append((url, params))
        if url == module.FORECAST_URL:
            if "open-meteo" in self.down:
                return answer(url, 503)
            return answer(url, payload=OPEN_METEO)
        if "openweather" in self.down:
            raise httpx.ConnectTimeout("sem rede")
        return answer(url, payload=OPENWEATHER)

    def urls(self):
        return [url for url, _ in self.calls]


def test_open_meteo_answers_first_and_is_cached(monkeypatch):
    apis = FakeApis()
    monkeypatch.setattr(module.httpx, "get", apis)
    climate = OpenMeteoClimate(backups=[OpenWeatherMapWeather("chave-de-teste")])
    assert climate.outside(-22.9056, -47.0608) == Outside(27.4, 61.0, "Open-Meteo")
    assert climate.outside(-22.9056, -47.0608) == Outside(27.4, 61.0, "Open-Meteo")
    assert apis.urls() == [module.FORECAST_URL]


def test_openweathermap_takes_over_when_open_meteo_fails(monkeypatch):
    apis = FakeApis(down={"open-meteo"})
    monkeypatch.setattr(module.httpx, "get", apis)
    climate = OpenMeteoClimate(backups=[OpenWeatherMapWeather("chave-de-teste")])
    assert climate.outside(-22.9056, -47.0608) == Outside(26.1, 64.0, "OpenWeatherMap")
    assert apis.calls[1] == (
        module.OPENWEATHER_URL,
        {"lat": -22.9056, "lon": -47.0608, "units": "metric", "appid": "chave-de-teste"},
    )


def test_last_value_is_kept_when_every_source_fails(monkeypatch):
    monkeypatch.setattr(module.httpx, "get", FakeApis())
    climate = OpenMeteoClimate(backups=[OpenWeatherMapWeather("chave-de-teste")])
    first = climate.outside(-22.9056, -47.0608)
    key = (-22.906, -47.061)
    saved_at, value = climate._cache[key]
    climate._cache[key] = (saved_at - module.CACHE_SECONDS - 1, value)

    monkeypatch.setattr(module.httpx, "get", FakeApis(down={"open-meteo", "openweather"}))
    assert climate.outside(-22.9056, -47.0608) == first
    assert climate.outside(-23.5505, -46.6333) is None


def test_broken_answer_falls_back_to_the_next_source(monkeypatch):
    def broken_open_meteo(url, params, timeout):
        if url == module.FORECAST_URL:
            return answer(url, payload={"current": {"temperature_2m": None}})
        return answer(url, payload=OPENWEATHER)

    monkeypatch.setattr(module.httpx, "get", broken_open_meteo)
    climate = OpenMeteoClimate(backups=[OpenWeatherMapWeather("chave-de-teste")])
    assert climate.outside(-22.9056, -47.0608).source == "OpenWeatherMap"


def test_openweathermap_is_used_only_with_a_key():
    def settings(**changes):
        return Settings(
            database_url="postgresql+psycopg://test@localhost/movement_test",
            session_secret=secrets.token_urlsafe(32),
            operator_password_hash=hash_password("operator-password"),
            retention_enabled=False,
            **changes,
        )

    without = create_app(settings(openweather_api_key=None)).state.climate
    assert [type(source).__name__ for source in without.sources] == ["OpenMeteoWeather"]
    with_key = create_app(settings(openweather_api_key="chave-de-teste")).state.climate
    assert [type(source).__name__ for source in with_key.sources] == [
        "OpenMeteoWeather",
        "OpenWeatherMapWeather",
    ]


def test_failed_sources_are_not_asked_again_for_a_minute(monkeypatch):
    apis = FakeApis(down={"open-meteo", "openweather"})
    monkeypatch.setattr(module.httpx, "get", apis)
    climate = OpenMeteoClimate(backups=[OpenWeatherMapWeather("chave-de-teste")])
    assert climate.outside(-22.9056, -47.0608) is None
    assert climate.outside(-22.9056, -47.0608) is None
    assert len(apis.calls) == 2
    key = (-22.906, -47.061)
    climate._failed[key] -= module.RETRY_SECONDS + 1
    assert climate.outside(-22.9056, -47.0608) is None
    assert len(apis.calls) == 4


def test_device_never_waits_for_the_weather(monkeypatch):
    apis = FakeApis()
    monkeypatch.setattr(module.httpx, "get", apis)
    pending = []
    climate = OpenMeteoClimate(background=pending.append)
    assert climate.outside_cached(-22.9056, -47.0608) is None
    assert climate.outside_cached(-22.9056, -47.0608) is None
    assert (len(pending), apis.calls) == (1, [])
    pending.pop()()
    assert climate.outside_cached(-22.9056, -47.0608) == Outside(27.4, 61.0, "Open-Meteo")
    assert (len(pending), len(apis.calls)) == (0, 1)
    key = (-22.906, -47.061)
    saved_at, value = climate._cache[key]
    climate._cache[key] = (saved_at - module.CACHE_SECONDS - 1, value)
    assert climate.outside_cached(-22.9056, -47.0608) == value
    assert len(pending) == 1
