import asyncio
from contextlib import asynccontextmanager, suppress
from datetime import UTC, datetime
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Query, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import AwareDatetime
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.auth import authenticate, issue_principal_session
from app.catalog import create_catalog_router
from app.database import build_session_factory
from app.dependencies import CurrentUser, Db, require_device, require_user
from app.management import create_management_router
from app.models import Device
from app.reports import create_reports_router
from app.repository import DuplicateConflict, PostgresTelemetryRepository, room_exists
from app.retention import retention_loop
from app.sampling import create_sampling_router
from app.schemas import (
    CurrentUserResponse,
    LatestResponse,
    LoginRequest,
    ReadingResponse,
    SessionResponse,
    TelemetryInput,
    TelemetryReceipt,
)
from app.settings import Settings, get_settings
from app.users import create_users_router

SCHEMA_VERSION = "0004_alerts"


def create_app(settings: Settings | None = None) -> FastAPI:
    config = settings or get_settings()
    sessions = build_session_factory(config)

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        task = (
            asyncio.create_task(retention_loop(sessions, config.retention_interval_seconds))
            if config.retention_enabled
            else None
        )
        try:
            yield
        finally:
            if task:
                task.cancel()
                with suppress(asyncio.CancelledError):
                    await task
            sessions.kw["bind"].dispose()

    app = FastAPI(title="Movement — Gestão de climatização", version="2.0.0", lifespan=lifespan)
    app.state.settings = config
    app.state.sessions = sessions
    app.add_middleware(
        CORSMiddleware,
        allow_origins=config.cors_origins,
        allow_methods=["GET", "POST", "PUT", "DELETE"],
        allow_headers=["Authorization", "Content-Type"],
        expose_headers=["Content-Disposition"],
    )

    @app.middleware("http")
    async def prevent_sensitive_cache(request: Request, call_next):
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store"
        return response

    @app.get("/health", tags=["Operação"])
    def health():
        return {"status": "ok", "version": "2.0.0"}

    @app.get("/ready", tags=["Operação"])
    def readiness(session: Db):
        try:
            version = session.scalar(text("SELECT version_num FROM alembic_version"))
            if version != SCHEMA_VERSION:
                raise HTTPException(503, "Migrações pendentes")
            session.execute(
                text(
                    "SELECT 1 FROM sensor_readings, air_conditioners, monthly_summaries, "
                    "units, users, ac_catalog, alerts LIMIT 1"
                )
            )
        except SQLAlchemyError:
            raise HTTPException(503, "Banco indisponível ou migrações pendentes") from None
        return {"status": "ready"}

    @app.post("/auth/login", response_model=SessionResponse, tags=["Autenticação"])
    def login(payload: LoginRequest, session: Db):
        result = authenticate(session, config, payload.username, payload.password)
        if result is None:
            raise HTTPException(401, "Usuário ou senha inválidos")
        principal, password_hash = result
        return SessionResponse(
            access_token=issue_principal_session(config, principal, password_hash),
            expires_in=config.session_ttl_seconds,
            user=CurrentUserResponse.of(principal),
        )

    @app.get("/auth/me", response_model=CurrentUserResponse, tags=["Autenticação"])
    def me(principal: CurrentUser):
        return CurrentUserResponse.of(principal)

    @app.post("/telemetry", response_model=TelemetryReceipt, status_code=201, tags=["Dispositivo"])
    def telemetry(
        payload: TelemetryInput,
        response: Response,
        session: Db,
        device: Annotated[Device, Depends(require_device)],
    ):
        try:
            reading, duplicate = PostgresTelemetryRepository(session).save(device, payload)
        except DuplicateConflict:
            raise HTTPException(409, "message_id já utilizado com outra leitura") from None
        if duplicate:
            response.status_code = 200
        return TelemetryReceipt(
            duplicate=duplicate, reading=ReadingResponse.model_validate(reading)
        )

    @app.get(
        "/rooms/{room_id}/latest",
        response_model=LatestResponse,
        dependencies=[Depends(require_user)],
        tags=["Leituras"],
    )
    def latest(room_id: str, session: Db):
        if not room_exists(session, room_id):
            raise HTTPException(404, "Ambiente não encontrado")
        reading = PostgresTelemetryRepository(session).latest(room_id)
        age = max(0, (datetime.now(UTC) - reading.measured_at).total_seconds()) if reading else None
        return LatestResponse(
            reading=ReadingResponse.model_validate(reading) if reading else None,
            age_seconds=age,
            is_stale=age is None or age > config.stale_after_seconds,
        )

    @app.get(
        "/rooms/{room_id}/history",
        response_model=list[ReadingResponse],
        dependencies=[Depends(require_user)],
        tags=["Leituras"],
    )
    def history(
        room_id: str,
        session: Db,
        limit: Annotated[int, Query(ge=1, le=2000)] = 500,
        since: AwareDatetime | None = None,
    ):
        if not room_exists(session, room_id):
            raise HTTPException(404, "Ambiente não encontrado")
        return PostgresTelemetryRepository(session).history(room_id, limit, since)

    app.include_router(create_management_router())
    app.include_router(create_catalog_router())
    app.include_router(create_users_router())
    app.include_router(create_reports_router())
    app.include_router(create_sampling_router())
    return app
