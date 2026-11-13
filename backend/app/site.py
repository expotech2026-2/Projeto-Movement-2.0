from pathlib import Path

from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.middleware.gzip import GZipMiddleware
from starlette.routing import Mount
from starlette.staticfiles import StaticFiles

from app.main import create_app
from app.settings import Settings

FRONTEND_DIST = Path(__file__).resolve().parents[2] / "frontend" / "dist"
ONE_YEAR = "public, max-age=31536000, immutable"


class SiteFiles(StaticFiles):
    """O Vite põe um hash no nome de cada arquivo de assets/: o navegador pode guardá-los."""

    def file_response(self, full_path, stat_result, scope, status_code=200):
        response = super().file_response(full_path, stat_result, scope, status_code)
        hashed = "assets" in Path(full_path).parts
        response.headers["Cache-Control"] = ONE_YEAR if hashed else "no-cache"
        return response


def create_site(settings: Settings | None = None, frontend: Path = FRONTEND_DIST) -> Starlette:
    api = create_app(settings)
    # Site na raiz e API em /api, o mesmo caminho do proxy do Vite em desenvolvimento.
    return Starlette(
        routes=[
            Mount("/api", app=api),
            Mount("/", app=SiteFiles(directory=frontend, html=True)),
        ],
        middleware=[Middleware(GZipMiddleware, minimum_size=1024)],
        lifespan=lambda _site: api.router.lifespan_context(api),
    )
