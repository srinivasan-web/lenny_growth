import logging

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.chat import router as chat_router
from app.api.content import router as content_router
from app.api.health import router as health_router
from app.api.sessions import router as sessions_router
from app.config import get_settings

logger = logging.getLogger(__name__)


def create_app() -> FastAPI:
    settings = get_settings()
    logging.basicConfig(level=settings.log_level, format="%(asctime)s %(levelname)s %(name)s %(message)s")

    app = FastAPI(title="Lenny Growth Assistant API", version="0.1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=False,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type", "Authorization"],
    )
    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(request, exc):
        return JSONResponse(status_code=422, content={"detail": "Invalid request.", "errors": exc.errors()})

    @app.exception_handler(Exception)
    async def unhandled_error_handler(request, exc):
        logger.exception("unhandled_api_error", extra={"path": request.url.path})
        return JSONResponse(status_code=500, content={"detail": "Internal server error."})
    app.include_router(health_router, prefix=settings.api_prefix)
    app.include_router(sessions_router, prefix=settings.api_prefix)
    app.include_router(chat_router, prefix=settings.api_prefix)
    app.include_router(content_router, prefix=settings.api_prefix)
    return app


app = create_app()
