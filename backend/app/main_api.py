from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app.api.auth import router as auth_router
from app.api.billing import router as billing_router
from app.api.items import router as items_router
from app.api.me import router as me_router
from app.api.scan import router as scan_router
from app.api.settings import router as settings_router
from app.api.webhooks import router as webhooks_router
from app.config import Settings, get_settings
from app.core.errors import register_exception_handlers
from app.core.logging import get_logger, setup_logging


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    yield


def create_app(settings: Settings | None = None) -> FastAPI:
    config = settings or get_settings()
    setup_logging()

    app = FastAPI(title="NeverMiss API", version=__version__, lifespan=lifespan)
    register_exception_handlers(app)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=config.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(auth_router)
    app.include_router(me_router)
    app.include_router(scan_router)
    app.include_router(settings_router)
    app.include_router(items_router)
    app.include_router(billing_router)
    # Webhook router is intentionally last and has no JWT auth dependency.
    # Never add get_current_user to this router.
    app.include_router(webhooks_router)

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok", "version": __version__}

    get_logger("app.main").info("api_app_created")

    return app


app = create_app()
