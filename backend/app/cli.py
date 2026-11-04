import argparse
import getpass
import secrets

from psycopg import Error as PostgresError
from sqlalchemy import select

from app.database import build_session_factory
from app.management import default_unit
from app.models import Device, Room
from app.security import hash_device_token, hash_password
from app.settings import get_settings


def main():
    parser = argparse.ArgumentParser(description="Administração local do Movement")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("password-hash", help="Gerar hash de senha sem exibir a senha")
    sub.add_parser("retain", help="Consolidar leituras antigas e aplicar retenção")
    local = sub.add_parser("local", help="Configurar e controlar PostgreSQL nativo do projeto")
    local.add_argument("action", choices=["setup", "start", "stop", "status"])
    local.add_argument("--port", type=int, default=5433)
    local.add_argument("--postgres-bin")
    catalog = sub.add_parser(
        "catalog-import", help="Recarregar o catálogo Inmetro de condicionadores de ar"
    )
    catalog.add_argument("--file", help="CSV gerado por scripts/inmetro_catalog.py")
    device = sub.add_parser("create-device", help="Cadastrar ambiente e dispositivo")
    device.add_argument("--room", required=True)
    device.add_argument("--name", required=True)
    device.add_argument("--device", required=True)
    args = parser.parse_args()
    if args.command == "retain":
        from app.retention import consolidate

        sessions = build_session_factory(get_settings())
        try:
            with sessions() as session:
                print(consolidate(session))
        finally:
            sessions.kw["bind"].dispose()
        return
    if args.command == "catalog-import":
        from pathlib import Path

        from app.catalog import CATALOG_CSV, read_catalog, replace_catalog

        try:
            rows = read_catalog(Path(args.file) if args.file else CATALOG_CSV)
        except (OSError, KeyError, ValueError) as error:
            parser.exit(1, f"Catálogo inválido: {error}\n")
        sessions = build_session_factory(get_settings())
        try:
            with sessions() as session:
                print(f"{replace_catalog(session, rows)} modelos carregados no catálogo.")
        finally:
            sessions.kw["bind"].dispose()
        return
    if args.command == "local":
        from app.localdev import LocalSetupError, run_local

        if not 1024 <= args.port <= 65535:
            parser.error("Porta deve estar entre 1024 e 65535")
        try:
            run_local(args.action, args.port, args.postgres_bin)
        except (LocalSetupError, PostgresError) as error:
            message = (
                str(error) if isinstance(error, LocalSetupError) else "Falha no PostgreSQL local."
            )
            parser.exit(1, message + "\n")
        return
    if args.command == "password-hash":
        password = getpass.getpass("Senha do operador (mínimo 12 caracteres): ")
        if len(password) < 12:
            parser.error("Use pelo menos 12 caracteres")
        if password != getpass.getpass("Confirme a senha: "):
            parser.error("Senhas diferentes")
        print(hash_password(password))
        return
    for identifier in (args.room, args.device):
        if not identifier or len(identifier) > 64:
            parser.error("Identificadores devem ter de 1 a 64 caracteres")
    if len(args.name) > 120:
        parser.error("Nome do ambiente deve ter no máximo 120 caracteres")
    sessions = build_session_factory(get_settings())
    try:
        with sessions() as session:
            if session.get(Device, args.device) or session.scalar(
                select(Device).where(Device.room_id == args.room)
            ):
                parser.error(
                    "Dispositivo ou ambiente já cadastrado; nenhuma credencial foi alterada"
                )
            if session.get(Room, args.room) is None:
                session.add(Room(id=args.room, name=args.name, unit_id=default_unit(session).id))
                session.flush()
            token = secrets.token_urlsafe(32)
            session.add(
                Device(id=args.device, room_id=args.room, token_hash=hash_device_token(token))
            )
            session.commit()
        print("Credencial do dispositivo (guarde fora do Git; exibida apenas agora):")
        print(token)
    finally:
        sessions.kw["bind"].dispose()
