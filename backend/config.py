import os
import logging
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

_REQUIRED = [
    "DATABASE_URL",
    "SUPABASE_URL",
    "CELERY_BROKER_URL",
    "CELERY_RESULT_BACKEND",
    "CLOUDFLARE_R2_ENDPOINT",
    "CLOUDFLARE_R2_ACCESS_KEY_ID",
    "CLOUDFLARE_R2_SECRET_ACCESS_KEY",
    "CLOUDFLARE_R2_BUCKET_NAME",
    "ANTHROPIC_API_KEY",
    "RESEND_API_KEY",
]

_OPTIONAL = {
    "HF_TOKEN": None,
    "CORS_ORIGINS": "http://localhost:3000",
}


def validate_env() -> None:
    missing = [k for k in _REQUIRED if not os.getenv(k)]
    if missing:
        raise RuntimeError(
            f"Missing required environment variables: {', '.join(missing)}\n"
            "Copy backend/.env.example to backend/.env and fill in the values."
        )
    logger.info("Environment validation passed.")


# ── Typed accessors ────────────────────────────────────────────

DATABASE_URL: str = os.getenv("DATABASE_URL", "")
SUPABASE_URL: str = os.getenv("SUPABASE_URL", "")
CELERY_BROKER_URL: str = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0")
CELERY_RESULT_BACKEND: str = os.getenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/0")

R2_ENDPOINT: str = os.getenv("CLOUDFLARE_R2_ENDPOINT", "")
R2_ACCESS_KEY_ID: str = os.getenv("CLOUDFLARE_R2_ACCESS_KEY_ID", "")
R2_SECRET_ACCESS_KEY: str = os.getenv("CLOUDFLARE_R2_SECRET_ACCESS_KEY", "")
R2_BUCKET_NAME: str = os.getenv("CLOUDFLARE_R2_BUCKET_NAME", "moodmap-audio")

HF_TOKEN: str | None = os.getenv("HF_TOKEN")
ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")
RESEND_API_KEY: str = os.getenv("RESEND_API_KEY", "")

CORS_ORIGINS: list[str] = [
    o.strip()
    for o in os.getenv("CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000").split(",")
    if o.strip()
]
