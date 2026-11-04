from pathlib import Path

from starlette.applications import Starlette
from starlette.routing import Mount
from starlette.staticfiles import StaticFiles

from app.main import create_app
from app.settings import Settings

FRONTEND_DIST = Path(__file__).resolve().parents[2] / "frontend" / "dist"


def create_site(settings: Settings | None = None, frontend: Path = FRONTEND_DIST) -> Starlette:
    api = create_app(settings)
    # Site na raiz e API em /api, o mesmo caminho do proxy do Vite em desenvolvimento.
    return Starlette(
        routes=[
            Mount("/api", app=api),
            Mount("/", app=StaticFiles(directory=frontend, html=True)),
        ],
        lifespan=lambda _site: api.router.lifespan_context(api),
    )
