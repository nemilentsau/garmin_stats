"""FastAPI app factory and HTTP-level setup."""

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from ..core.config import get_cors_origins
from ..infra.database import DATA_DIR
from .lifespan import lifespan
from .routing import register_routers


async def lookup_error_handler(_request: Request, exc: LookupError) -> JSONResponse:
    return JSONResponse(status_code=404, content={"detail": str(exc)})


async def value_error_handler(_request: Request, exc: ValueError) -> JSONResponse:
    return JSONResponse(status_code=400, content={"detail": str(exc)})


async def disable_api_response_caching(request: Request, call_next):
    """Mark API responses as non-cacheable unless a route sets its own policy."""
    response = await call_next(request)
    if request.url.path.startswith("/api/") and "Cache-Control" not in response.headers:
        response.headers["Cache-Control"] = "no-store"
        response.headers["Pragma"] = "no-cache"
    return response


def create_app() -> FastAPI:
    app = FastAPI(
        title="Garmin Stats API",
        description="API for analyzing Garmin Epix Gen 2 health data",
        version="0.1.0",
        separate_input_output_schemas=True,
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=get_cors_origins(),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.exception_handler(LookupError)(lookup_error_handler)
    app.exception_handler(ValueError)(value_error_handler)
    app.middleware("http")(disable_api_response_caching)

    register_routers(app)

    @app.get("/")
    def root():
        """API root - health check."""
        return {
            "status": "ok",
            "message": "Garmin Stats API",
            "data_dir": str(DATA_DIR),
            "data_exists": DATA_DIR.exists(),
        }

    return app
