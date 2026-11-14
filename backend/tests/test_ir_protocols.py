import time

from app.ir_protocols import brand_candidate, lookup


def test_brand_candidate_only_when_model_is_unknown():
    assert brand_candidate(" lg ") == {
        "protocol": "LG2",
        "ir_model": 2,
        "confidence": "brand_candidate",
    }
    assert brand_candidate("Springer Midea")["protocol"] == "COOLIX"
    assert brand_candidate("FUJITSU/AIRSTAGE")["protocol"] == "FUJITSU_AC"
    assert brand_candidate("Elgin")["protocol"] == "COOLIX"
    assert brand_candidate("AGRATTO")["protocol"] == "TCL112AC"
    assert brand_candidate("Philco")["protocol"] == "MIRAGE"
    assert brand_candidate("ELECTROLUX") is None
    assert brand_candidate("") is None


def test_model_lookup_does_not_guess_by_brand():
    assert lookup("LG", " s4 w12ja3aa ")["protocol"] == "LG2"
    assert lookup("LG", "desconhecido") is None
    assert lookup("OUTRA", "S4-W12JA3AA") is None
    assert lookup("SAMSUNG", "AR24BVFAAWKNAZ")["confidence"] == "family_candidate"


def test_protocols_saved_and_sent_only_to_the_room_device(context):
    client = context["client"]
    room = context["room"]
    payload = {
        "name": "Ar Samsung",
        "kind": "split",
        "brand": "SAMSUNG",
        "model": "AR24BVFAAWKNAZ",
        "capacity_btu": 22000,
    }
    response = client.post(
        f"/rooms/{room}/appliances", headers=context["operator_headers"], json=payload
    )
    assert response.status_code == 201
    saved = response.json()
    assert saved["ir_protocol"] == "SAMSUNG_AC"
    assert saved["ir_source"] == "family_candidate"
    device = client.get("/devices/me/control", headers=context["device_headers"])
    assert device.status_code == 200
    assert device.json()["ir_protocols"] == "SAMSUNG_AC:1"
    assert device.json()["ir_pending"] == 0
    second = client.post(
        f"/rooms/{room}/appliances",
        headers=context["operator_headers"],
        json={**payload, "name": "Ar LG", "brand": "LG", "model": "S4-W12JA3AA"},
    )
    assert second.status_code == 201
    assert (
        client.get("/devices/me/control", headers=context["device_headers"]).json()["ir_protocols"]
        == "LG2:2,SAMSUNG_AC:1"
    )
    updated = client.put(
        f"/rooms/{room}/appliances/{saved['id']}",
        headers=context["operator_headers"],
        json={**payload, "status": "inativo"},
    )
    assert updated.status_code == 200
    assert (
        client.get("/devices/me/control", headers=context["device_headers"]).json()["ir_protocols"]
        == "LG2:2"
    )
    assert client.get("/devices/me/control").status_code == 401
    other = client.post(
        "/rooms",
        headers=context["operator_headers"],
        json={"name": "Outra sala", "unit_id": context["unit"]},
    ).json()
    credential = client.post(
        f"/rooms/{other['id']}/devices", headers=context["operator_headers"]
    ).json()
    other_headers = {"Authorization": f"Bearer {credential['token']}"}
    assert client.get("/devices/me/control", headers=other_headers).json()["ir_protocols"] == ""


def test_unknown_model_remains_pending_and_manual_protocol_is_validated(context):
    client, headers = context["client"], context["operator_headers"]
    path = f"/rooms/{context['room']}/appliances"
    payload = {"name": "Sem modelo", "kind": "split", "capacity_btu": 9000}
    saved = client.post(path, headers=headers, json=payload).json()
    assert saved["ir_protocol"] is None
    assert saved["ir_source"] == "pending"
    assert (
        client.get("/devices/me/control", headers=context["device_headers"]).json()["ir_pending"]
        == 1
    )
    assert (
        client.post(path, headers=headers, json={**payload, "ir_protocol": "INVALIDO"}).status_code
        == 422
    )
    manual = client.post(path, headers=headers, json={**payload, "ir_protocol": "GREE"})
    assert manual.json()["ir_source"] == "manual"
    zh = client.post(path, headers=headers, json={**payload, "ir_protocol": "NEOCLIMA"}).json()
    assert (zh["ir_protocol"], zh["ir_model"], zh["ir_source"]) == ("NEOCLIMA", 1, "manual")
    control = client.get("/devices/me/control", headers=context["device_headers"]).json()
    assert "NEOCLIMA:1" in control["ir_protocols"].split(",")


def test_inmetro_model_gets_brand_candidate_and_reaches_device(context):
    client, headers = context["client"], context["operator_headers"]
    path = f"/rooms/{context['room']}/appliances"
    payload = {
        "name": "Ar Gree",
        "kind": "split",
        "brand": "GREE",
        "model": "GWC12QC-D3NNB4D",
        "capacity_btu": 12000,
    }
    saved = client.post(path, headers=headers, json=payload).json()
    assert (saved["ir_protocol"], saved["ir_model"], saved["ir_source"]) == (
        "GREE",
        1,
        "brand_candidate",
    )
    control = client.get("/devices/me/control", headers=context["device_headers"]).json()
    assert (control["ir_protocols"], control["ir_pending"]) == ("GREE:1", 0)
    unknown = client.post(path, headers=headers, json={**payload, "brand": "ELECTROLUX"}).json()
    assert (unknown["ir_protocol"], unknown["ir_source"]) == (None, "pending")
    manual = client.put(
        f"{path}/{saved['id']}", headers=headers, json={**payload, "ir_protocol": "KELVINATOR"}
    ).json()
    assert (manual["ir_protocol"], manual["ir_source"]) == ("KELVINATOR", "manual")
    resend = client.post(f"/rooms/{context['room']}/ir-protocol", headers=headers).json()
    assert (resend["protocols"], resend["candidates"]) == ("KELVINATOR:1", 0)


def test_migration_fills_brand_candidate_only_for_pending(database_url):
    from pathlib import Path
    from uuid import uuid4

    from alembic import command
    from alembic.config import Config
    from sqlalchemy import create_engine, text

    schema = f"ir_brand_{uuid4().hex}"
    engine = create_engine(database_url)
    with engine.begin() as connection:
        connection.execute(text(f'CREATE SCHEMA "{schema}"'))
        connection.execute(text(f'SET LOCAL search_path TO "{schema}"'))
        config = Config(str(Path(__file__).parents[1] / "alembic.ini"))
        config.attributes["connection"] = connection
        command.upgrade(config, "0009_appliance_ir")
        connection.execute(text("INSERT INTO units (id, name) VALUES ('u', 'Unidade')"))
        connection.execute(text("INSERT INTO rooms (id, name, unit_id) VALUES ('r', 'Sala', 'u')"))
        rows = [
            ("pendente", "Springer Midea", None, "pending"),
            ("manual", "LG", "GREE", "manual"),
            ("desconhecida", "Elgin", None, "pending"),
        ]
        for name, brand, protocol, source in rows:
            connection.execute(
                text(
                    "INSERT INTO air_conditioners (id, room_id, name, kind, brand, model, "
                    "capacity_btu, inverter, status, ir_protocol, ir_source) VALUES "
                    "(:id, 'r', :name, 'split', :brand, 'X', 9000, false, 'ativo', "
                    ":protocol, :source)"
                ),
                {
                    "id": uuid4(),
                    "name": name,
                    "brand": brand,
                    "protocol": protocol,
                    "source": source,
                },
            )
        query = text("SELECT name, ir_protocol, ir_source FROM air_conditioners ORDER BY name")
        command.upgrade(config, "0010_ir_brand_candidate")
        assert connection.execute(query).all() == [
            ("desconhecida", None, "pending"),
            ("manual", "GREE", "manual"),
            ("pendente", "COOLIX", "brand_candidate"),
        ]
        command.upgrade(config, "0012_ir_more_brands")
        assert connection.execute(query).all()[0] == ("desconhecida", "COOLIX", "brand_candidate")
        command.downgrade(config, "0011_ir_transport")
        assert connection.execute(query).all() == [
            ("desconhecida", None, "pending"),
            ("manual", "GREE", "manual"),
            ("pendente", "COOLIX", "brand_candidate"),
        ]
        command.downgrade(config, "0009_appliance_ir")
        assert connection.execute(query).all()[2] == ("pendente", None, "pending")
        connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
    engine.dispose()


def test_migration_backfills_existing_model(database_url):
    from pathlib import Path
    from uuid import uuid4

    from alembic import command
    from alembic.config import Config
    from sqlalchemy import create_engine, text

    schema = f"ir_migration_{uuid4().hex}"
    engine = create_engine(database_url)
    with engine.begin() as connection:
        connection.execute(text(f'CREATE SCHEMA "{schema}"'))
        connection.execute(text(f'SET LOCAL search_path TO "{schema}"'))
        config = Config(str(Path(__file__).parents[1] / "alembic.ini"))
        config.attributes["connection"] = connection
        command.upgrade(config, "0008_room_heat")
        connection.execute(text("INSERT INTO units (id, name) VALUES ('u', 'Unidade')"))
        connection.execute(text("INSERT INTO rooms (id, name, unit_id) VALUES ('r', 'Sala', 'u')"))
        connection.execute(
            text(
                "INSERT INTO air_conditioners "
                "(id, room_id, name, kind, brand, model, capacity_btu, inverter, status) "
                "VALUES (:id, 'r', 'Ar', 'split', 'Samsung', "
                "'AR24BVFAAWKNAZ', 22000, false, 'ativo')"
            ),
            {"id": uuid4()},
        )
        import importlib.util

        from alembic.migration import MigrationContext
        from alembic.operations import Operations

        migration = Path(__file__).parents[1] / "migrations/versions/0009_appliance_ir.py"
        spec = importlib.util.spec_from_file_location("expand_ir_test", migration)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with Operations.context(MigrationContext.configure(connection)):
            module.upgrade()
            module.upgrade()
        assert (
            connection.scalar(text("SELECT version_num FROM alembic_version")) == "0008_room_heat"
        )
        command.upgrade(config, "head")
        assert connection.execute(
            text("SELECT ir_protocol, ir_model, ir_source FROM air_conditioners")
        ).one() == ("SAMSUNG_AC", 1, "family_candidate")
        command.downgrade(config, "0008_room_heat")
        command.upgrade(config, "head")
        assert connection.scalar(text("SELECT ir_protocol FROM air_conditioners")) == "SAMSUNG_AC"
        connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
    engine.dispose()


def test_admin_can_resend_protocol_without_changing_ac_command(context):
    client, headers = context["client"], context["operator_headers"]
    room = context["room"]
    path = f"/rooms/{room}/ir-protocol"
    assert client.post(path).status_code == 401
    assert client.post(path, headers=context["professor_headers"]).status_code == 403
    assert client.post(path, headers=headers).status_code == 409
    client.post(
        f"/rooms/{room}/appliances",
        headers=headers,
        json={
            "name": "Ar",
            "kind": "split",
            "capacity_btu": 22000,
            "brand": "SAMSUNG",
            "model": "AR24BVFAAWKNAZ",
        },
    )

    def device_view():
        body = client.get("/devices/me/control", headers=context["device_headers"]).json()
        assert abs(body.pop("server_time") - time.time()) < 60
        return body

    before = device_view()
    for revision in (1, 2):
        result = client.post(path, headers=headers)
        assert result.status_code == 200
        assert result.json()["revision"] == revision
        assert result.json()["protocols"] == "SAMSUNG_AC:1"
        assert result.json()["candidates"] == 1
        assert device_view() == {**before, "ir_revision": revision}
