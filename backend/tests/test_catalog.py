from app.catalog import CATALOG_KINDS, catalog_metadata, read_catalog


def test_bundled_catalog_is_consistent_with_its_metadata():
    rows = read_catalog()
    metadata = catalog_metadata()
    assert len(rows) == metadata["models"]
    assert len({row["brand"] for row in rows}) == metadata["brands"]
    assert sum(row["corrected"] for row in rows) == metadata["corrected"]
    assert all(row["kind"] in CATALOG_KINDS for row in rows)
    assert all(1000 <= row["capacity_btu"] <= 500000 for row in rows)
    assert all(row["registration"] and row["energy_class"] for row in rows)


def test_catalog_lists_brands_and_filters_models(context):
    client, teacher = context["client"], context["professor_headers"]
    assert client.get("/catalog/brands").status_code == 401
    rows = read_catalog()
    info = client.get("/catalog", headers=teacher).json()
    assert info["models"] == len(rows)
    assert info["updated_at"] == catalog_metadata()["updated_at"]
    brands = {
        item["brand"]: item["models"]
        for item in client.get("/catalog/brands", headers=teacher).json()
    }
    assert {"LG", "SAMSUNG", "GREE", "MIDEA"} <= set(brands)
    assert sum(brands.values()) == len(rows)
    models = client.get(
        "/catalog/models", headers=teacher, params={"brand": "gree", "kind": "split"}
    ).json()
    assert models and all(item["brand"] == "GREE" and item["kind"] == "split" for item in models)
    assert [item["capacity_btu"] for item in models] == sorted(
        item["capacity_btu"] for item in models
    )
    sample = models[0]["model"]
    found = client.get("/catalog/models", headers=teacher, params={"q": sample[:6]}).json()
    assert any(item["model"] == sample for item in found)
    assert client.get("/catalog/models", headers=teacher, params={"kind": "vrf"}).status_code == 422
