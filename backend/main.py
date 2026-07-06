"""FastAPI application entrypoint: app instance, middleware, and routers.

Run from inside this directory with:
    uvicorn main:app --reload

Created by Prarthna Gautam (https://github.com/prarthnagautam1094) — 2026.
Part of the Document Q&A project.
"""

import logging
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

import database
from config import settings
from models.schemas import HealthResponse
from routers import analytics, chat, documents

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Run once at startup: warn (but don't fail) if required config is missing.

    Missing GROQ_API_KEY shouldn't prevent /health or /docs from working —
    only the chat/rewrite calls that actually need it will fail, and only
    when someone hits them. Same principle for the database: init_db()
    itself never raises (see database.py) — a bad DATABASE_URL logs a
    clear error and leaves persistence disabled rather than taking down
    upload/chat, which don't depend on it.
    """
    if not settings.GROQ_API_KEY:
        logger.warning(
            "GROQ_API_KEY is not set — /chat/ask will fail until it's configured in .env."
        )
    database.init_db()
    yield


app = FastAPI(
    title="Document Q&A Backend",
    description=(
        "Retrieval-augmented Q&A over uploaded PDF documents. Upload PDFs "
        "via /documents/upload, then ask questions grounded in their "
        "content via /chat/ask."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

# Allow all origins for now — the frontend's deployed origin isn't fixed
# yet. Tighten this to an explicit allow-list before deploying anywhere
# public. allow_credentials is left False since no cookie/auth-based
# session is used yet; turning it on together with a wildcard origin is
# rejected by browsers anyway.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Log method, path, response status, and duration for every request.

    A single middleware covers this uniformly for every current and future
    endpoint, rather than repeating a log line by hand in each handler.
    """
    start_time = time.time()
    response = await call_next(request)
    duration_ms = (time.time() - start_time) * 1000
    logger.info(
        "%s %s -> %d (%.1fms)",
        request.method,
        request.url.path,
        response.status_code,
        duration_ms,
    )
    return response


app.include_router(documents.router)
app.include_router(chat.router)
app.include_router(analytics.router)


def _patch_openapi_schema() -> dict:
    """Generate the OpenAPI schema, then patch a Swagger UI file-upload gap.

    FastAPI represents a file field (UploadFile) purely with the OpenAPI
    3.1 / JSON Schema 2020-12 keyword `contentMediaType` (see
    fastapi.datastructures.UploadFile.__get_pydantic_json_schema__) and
    never emits the older OpenAPI 3.0 `format: "binary"` keyword. That's a
    spec-correct schema, but the Swagger UI bundle FastAPI's own /docs
    page loads (swagger-ui-dist, verified here at the latest 5.32.8) only
    recognizes `format: "binary"` on *array* items when deciding whether
    to render a file-picker widget — a single (non-array) UploadFile field
    renders correctly either way, but `list[UploadFile]` (the only way to
    accept multiple files) renders as a plain string-array editor with an
    "Add string item" button instead of a "Choose File" button.
    Overriding app.openapi() to add `format: "binary"` next to the
    existing `contentMediaType` on every such array-items schema fixes the
    /docs widget without touching request parsing (Pydantic validates
    against the route's actual type hints, not this generated schema) or
    the route signature itself.
    """
    if app.openapi_schema:
        return app.openapi_schema
    schema = FastAPI.openapi(app)
    for component_schema in schema.get("components", {}).get("schemas", {}).values():
        for prop in component_schema.get("properties", {}).values():
            items = prop.get("items")
            if isinstance(items, dict) and items.get("contentMediaType") == "application/octet-stream":
                items["format"] = "binary"
    app.openapi_schema = schema
    return app.openapi_schema


app.openapi = _patch_openapi_schema


@app.get(
    "/health",
    response_model=HealthResponse,
    tags=["health"],
    summary="Health check",
    description="Liveness check for load balancers / uptime monitors — always returns ok if the process is serving requests.",
)
def health_check() -> HealthResponse:
    """Return a simple liveness signal."""
    return HealthResponse(status="ok")



if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
