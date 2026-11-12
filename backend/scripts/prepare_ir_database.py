"""Expande o banco para IR sem invalidar a API 0008 ainda publicada."""

import argparse
import importlib.util
import json
from pathlib import Path

from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import text

from app.database import build_engine
from app.settings import Settings

BACKEND = Path(__file__).resolve().parents[1]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--schema", choices=("movement", "movement_dev"), required=True)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    settings = Settings(_env_file=BACKEND / ".env.supabase").model_copy(
        update={"database_schema": args.schema}
    )
    engine = build_engine(settings)
    migration = BACKEND / "migrations" / "versions" / "0009_appliance_ir.py"
    spec = importlib.util.spec_from_file_location("ir_expansion", migration)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    try:
        with engine.begin() as connection:
            connection.execute(text("SET LOCAL lock_timeout = '5s'"))
            connection.execute(text("SET LOCAL statement_timeout = '30s'"))
            connection.execute(text("SELECT pg_advisory_xact_lock(hashtext('movement-ir-expand'))"))
            revision = connection.scalar(text("SELECT version_num FROM alembic_version"))
            if revision not in ("0008_room_heat", "0009_appliance_ir"):
                raise RuntimeError("Revisão inesperada; nenhuma alteração aplicada")
            if not args.apply:
                print(json.dumps({"schema": args.schema, "revision": revision, "apply": False}))
                return
            connection.execute(
                text("LOCK TABLE rooms, air_conditioners IN ACCESS EXCLUSIVE MODE NOWAIT")
            )
            with Operations.context(MigrationContext.configure(connection)):
                module.upgrade()
            counts = connection.execute(
                text(
                    "SELECT count(*), count(ir_protocol), "
                    "count(*) FILTER (WHERE ir_source='family_candidate') FROM air_conditioners"
                )
            ).one()
            after = connection.scalar(text("SELECT version_num FROM alembic_version"))
            if after != revision:
                raise RuntimeError("A expansão não deve alterar a revisão da API publicada")
            print(
                json.dumps(
                    {
                        "schema": args.schema,
                        "revision_preserved": after,
                        "appliances": counts[0],
                        "with_protocol": counts[1],
                        "candidates": counts[2],
                    }
                )
            )
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
