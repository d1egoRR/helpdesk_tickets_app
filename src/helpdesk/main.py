from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from helpdesk.adapters.inbound.http.health import router as health_router
from helpdesk.config import Settings, get_settings


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    """Manage application startup and graceful shutdown lifecycle."""
    yield


def create_app(settings: Settings | None = None) -> FastAPI:
    """Create and configure the FastAPI application instance."""
    app_settings = settings or get_settings()
    app = FastAPI(
        title=app_settings.app_name,
        lifespan=lifespan,
    )
    app.include_router(health_router)
    return app


app = create_app()
