import time

import pytest
from pydantic import ValidationError

from app.ir_transport import TransportInput


@pytest.mark.parametrize(
    "url",
    [
        "http://192.168.1.150:8080/ac",
        "http://10.0.0.20:1821/ac",
        "http://172.31.1.1:65535/ac",
    ],
)
def test_local_gateway_url(url):
    assert TransportInput(transport="xiaomi", gateway_url=url).gateway_url == url


@pytest.mark.parametrize(
    "url",
    [
        "",
        "http://127.0.0.1:8080/ac",
        "http://169.254.169.254:8080/ac",
        "http://8.8.8.8:8080/ac",
        "http://xiaomi.local:8080/ac",
        "https://192.168.1.1:8080/ac",
        "http://192.168.1.1/ac",
        "http://192.168.1.1:80/ac",
        "http://192.168.1.1:65536/ac",
        "http://192.168.1.1:8080/ac?key=x",
        "http://user@192.168.1.1:8080/ac",
        "http://192.168.1.1:8080/ac#test",
        "http://192.168.1.1:8080/telemetry",
        "http://192.168.1.1:08080/ac",
        "http://192.168.1.1:8080/ac\n",
    ],
)
def test_rejects_nonlocal_or_ambiguous_gateway(url):
    with pytest.raises(ValidationError):
        TransportInput(transport="xiaomi", gateway_url=url)


def test_admin_choice_reaches_only_room_device_without_changing_ac_command(context):
    client = context["client"]
    path = f"/rooms/{context['room']}/ir-transport"
    before = client.get("/devices/me/control", headers=context["device_headers"]).json()
    assert abs(before.pop("server_time") - time.time()) < 60
    assert client.get(path).status_code == 401
    assert client.get(path, headers=context["device_headers"]).status_code == 401
    assert client.get(path, headers=context["professor_headers"]).json() == {
        "transport": "esp32",
        "gateway_url": "",
        "revision": 0,
    }
    body = {"transport": "xiaomi", "gateway_url": "http://192.168.1.150:8080/ac"}
    assert client.put(path, headers=context["professor_headers"], json=body).status_code == 403
    assert client.put(path, headers=context["device_headers"], json=body).status_code == 401
    for revision in (1, 2):
        saved = client.put(path, headers=context["operator_headers"], json=body)
        assert saved.status_code == 200
        assert saved.json() == {**body, "revision": revision}
        control = client.get("/devices/me/control", headers=context["device_headers"]).json()
        assert abs(control.pop("server_time") - time.time()) < 60
        assert control == {
            **before,
            "ir_transport": "xiaomi",
            "ir_gateway_url": body["gateway_url"],
            "ir_transport_revision": revision,
        }
    reverted = client.put(path, headers=context["operator_headers"], json={"transport": "esp32"})
    assert reverted.json() == {"transport": "esp32", "gateway_url": "", "revision": 3}
    assert (
        client.put(
            path, headers=context["operator_headers"], json={"transport": "wifi"}
        ).status_code
        == 422
    )
    assert (
        client.get(
            "/rooms/nao-existe/ir-transport", headers=context["operator_headers"]
        ).status_code
        == 404
    )


def test_other_room_keeps_its_emitter(context):
    client, headers = context["client"], context["operator_headers"]
    room = client.post(
        "/rooms", headers=headers, json={"name": "Outra sala", "unit_id": context["unit"]}
    ).json()
    client.put(
        f"/rooms/{room['id']}/ir-transport",
        headers=headers,
        json={"transport": "xiaomi", "gateway_url": "http://10.0.0.4:8080/ac"},
    )
    control = client.get("/devices/me/control", headers=context["device_headers"]).json()
    assert (
        control["ir_transport"],
        control["ir_gateway_url"],
        control["ir_transport_revision"],
    ) == (
        "esp32",
        "",
        0,
    )
