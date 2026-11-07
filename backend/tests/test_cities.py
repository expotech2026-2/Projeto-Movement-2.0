import httpx
import pytest

from app import cities as module
from app.cities import CitiesUnavailable, City, IbgeCities, city_source

IBGE = [
    {"municipio-id": 3509502, "municipio-nome": "Campinas", "UF-sigla": "SP"},
    {"municipio-id": 2201606, "municipio-nome": "Bom Jesus", "UF-sigla": "PI"},
]


def ibge_response(status=200, payload=None):
    request = httpx.Request("GET", module.IBGE_URL)
    return httpx.Response(status, json=IBGE if payload is None else payload, request=request)


def test_ibge_list_is_read_once_and_kept_when_the_ibge_fails(monkeypatch):
    calls = []

    def fake_get(url, params, timeout):
        calls.append(params)
        return ibge_response()

    monkeypatch.setattr(module.httpx, "get", fake_get)
    source = IbgeCities()
    assert source.cities() == [
        City(id=3509502, name="Campinas", state="SP"),
        City(id=2201606, name="Bom Jesus", state="PI"),
    ]
    assert source.cities()[0].name == "Campinas"
    assert calls == [{"view": "nivelado", "orderBy": "nome"}]

    source._loaded_at -= module.CACHE_SECONDS + 1
    monkeypatch.setattr(module.httpx, "get", lambda *args, **kwargs: ibge_response(503))
    assert len(source.cities()) == 2


def test_ibge_failure_without_a_list_is_reported(monkeypatch):
    def offline(*args, **kwargs):
        raise httpx.ConnectTimeout("sem rede")

    monkeypatch.setattr(module.httpx, "get", offline)
    with pytest.raises(CitiesUnavailable):
        IbgeCities().cities()
    monkeypatch.setattr(module.httpx, "get", lambda *a, **k: ibge_response(payload=[{"x": 1}]))
    with pytest.raises(CitiesUnavailable):
        IbgeCities().cities()


class FakeSource:
    def __init__(self, available=True):
        self.available = available

    def cities(self):
        if not self.available:
            raise CitiesUnavailable
        return [City(id=3509502, name="Campinas", state="SP")]


def test_cities_route_requires_login_and_reports_the_ibge_offline(context):
    client = context["client"]
    overrides = context["app"].dependency_overrides
    try:
        overrides[city_source] = lambda: FakeSource()
        assert client.get("/cities").status_code == 401
        response = client.get("/cities", headers=context["professor_headers"])
        assert response.status_code == 200
        assert response.json() == [{"id": 3509502, "name": "Campinas", "state": "SP"}]
        overrides[city_source] = lambda: FakeSource(available=False)
        offline = client.get("/cities", headers=context["professor_headers"])
        assert offline.status_code == 503
    finally:
        overrides.clear()
