import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import httpx
from app.database import build_session_factory
from app.models import AirConditioner, Device, Room, SensorReading
from app.settings import Settings
from sqlalchemy import delete


def main():
    root = Path(__file__).resolve().parents[1]
    instance = json.loads(
        (root / ".local/postgres-dev/instance.json").read_text(encoding="utf-8")
    )
    settings = Settings(_env_file=root / "backend/.env")
    if ":5433/Movement" not in settings.database_url.get_secret_value():
        raise SystemExit("Este teste HTTP exige o banco isolado Movement na porta 5433")
    room_id = None
    with httpx.Client(base_url="http://127.0.0.1:5173/api", timeout=15) as client:
        try:
            response = client.post(
                "/auth/login",
                json={"username": "admin", "password": instance["operator_password"]},
            )
            response.raise_for_status()
            client.headers["Authorization"] = (
                f"Bearer {response.json()['access_token']}"
            )
            response = client.post(
                "/rooms", json={"name": "Verificação HTTP", "capacity": 20}
            )
            response.raise_for_status()
            room_id = response.json()["id"]
            path = f"/rooms/{room_id}"
            response = client.post(
                f"{path}/appliances",
                json={"name": "Teste HTTP", "kind": "split", "capacity_btu": 12000},
            )
            response.raise_for_status()
            assert response.json()["room_id"] == room_id
            response = client.post(f"{path}/devices")
            response.raise_for_status()
            token = response.json()["token"]
            payload = {
                "message_id": str(uuid4()),
                "measured_at": datetime.now(UTC).isoformat(),
                "occupancy": 4,
                "temp_inside": 24,
                "temp_outside": 29,
                "humidity_inside": 50,
                "humidity_outside": 60,
                "target_temp": 23,
                "ac_on": True,
                "manual_mode": False,
            }
            response = client.post(
                "/telemetry", json=payload, headers={"Authorization": f"Bearer {token}"}
            )
            response.raise_for_status()
            assert client.get(f"{path}/latest").json()["reading"]["occupancy"] == 4
            assert len(client.get(f"{path}/history").json()) == 1
            assert client.get(f"{path}/monthly").json()[0]["avg_temp_inside"] == 24
            assert client.get("/ready").status_code == 200
            print(
                "HTTP: login, proxy React, salas, aparelhos, dispositivo, telemetria, histórico e média mensal verificados."
            )
        finally:
            if room_id:
                sessions = build_session_factory(settings)
                try:
                    with sessions() as session:
                        for model in (SensorReading, AirConditioner, Device):
                            session.execute(
                                delete(model).where(model.room_id == room_id)
                            )
                        session.execute(delete(Room).where(Room.id == room_id))
                        session.commit()
                finally:
                    sessions.kw["bind"].dispose()


if __name__ == "__main__":
    main()
