import os
import logging
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from backend.config import validate_env, CORS_ORIGINS
from backend.routers import user, journal, insights, nudges, reports, dashboard, account

# ── Structured JSON logging ───────────────────────────────────────────────────
try:
    from pythonjsonlogger import jsonlogger
    _log_handler = logging.StreamHandler()
    _log_handler.setFormatter(
        jsonlogger.JsonFormatter("%(asctime)s %(name)s %(levelname)s %(message)s")
    )
    logging.basicConfig(
        level=os.getenv("LOG_LEVEL", "INFO").upper(),
        handlers=[_log_handler],
        force=True,
    )
except ImportError:
    # Fallback to plain text if python-json-logger is not installed
    logging.basicConfig(
        level=os.getenv("LOG_LEVEL", "INFO").upper(),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )

logger = logging.getLogger(__name__)

# ── Optional Sentry ───────────────────────────────────────────────────────────
_sentry_dsn = os.getenv("SENTRY_DSN")
if _sentry_dsn:
    try:
        import sentry_sdk
        sentry_sdk.init(
            dsn=_sentry_dsn,
            environment=os.getenv("ENVIRONMENT", "production"),
            traces_sample_rate=0.1,
        )
        logger.info("Sentry initialised (environment=%s)", os.getenv("ENVIRONMENT"))
    except ImportError:
        logger.warning("SENTRY_DSN set but sentry-sdk not installed — skipping")

validate_env()

# ── Request body size limit ───────────────────────────────────────────────────
# Configurable via MAX_REQUEST_BODY_BYTES env var. Default: 1 MB.
# Cloudflare also enforces its own limit upstream (100 MB on free plan),
# but this middleware catches oversized bodies before they hit application logic.
_MAX_BODY_BYTES = int(os.getenv("MAX_REQUEST_BODY_BYTES", str(1 * 1024 * 1024)))


class MaxBodySizeMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        content_length = request.headers.get("content-length")
        if content_length and int(content_length) > _MAX_BODY_BYTES:
            return Response(
                content=f"Request body exceeds {_MAX_BODY_BYTES // 1024} KB limit.",
                status_code=413,
            )
        return await call_next(request)


app = FastAPI(title="MoodMap API")

app.add_middleware(MaxBodySizeMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    # Explicit allowlists: ["*"] with allow_credentials=True is widely
    # treated as a CORS misconfiguration. List only what the client uses.
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Accept"],
)

# ── Prometheus metrics (/metrics) ─────────────────────────────────────────────
try:
    from prometheus_fastapi_instrumentator import Instrumentator
    Instrumentator().instrument(app).expose(app, endpoint="/metrics")
    logger.info("Prometheus metrics available at /metrics")
except ImportError:
    logger.warning("prometheus-fastapi-instrumentator not installed — /metrics disabled")

app.include_router(user.router)
app.include_router(journal.router)
app.include_router(insights.router)
app.include_router(nudges.router)
app.include_router(reports.router)
app.include_router(dashboard.router)
app.include_router(account.router)


@app.get("/health")
def health_check():
    return {"status": "ok"}


@app.get("/")
def read_root():
    return {"message": "MoodMap API is running"}
