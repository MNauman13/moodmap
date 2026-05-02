import os
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from backend.models.db_models import Base

# Find the exact folder database.py is in, and load the .env file next to it
current_dir = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(current_dir, ".env"))

DATABASE_URL = os.getenv("DATABASE_URL")  # postgresql+asyncpg://...

# Guard: DATABASE_URL may be None during import in CI/test environments that
# provide a sqlite+aiosqlite URL instead. Replace only when the prefix matches.
if DATABASE_URL and DATABASE_URL.startswith("postgresql+asyncpg://"):
    SYNC_DATABASE_URL = DATABASE_URL.replace("postgresql+asyncpg://", "postgresql+psycopg2://")
elif DATABASE_URL and DATABASE_URL.startswith("sqlite+aiosqlite://"):
    SYNC_DATABASE_URL = DATABASE_URL.replace("sqlite+aiosqlite://", "sqlite:///")
else:
    SYNC_DATABASE_URL = DATABASE_URL  # let SQLAlchemy surface a meaningful error at startup

_is_postgres = DATABASE_URL and DATABASE_URL.startswith("postgresql")

# Async engine — used by FastAPI.
# pool_pre_ping: detect stale connections after DB proxy restarts (e.g. Railway).
# pool_size/max_overflow only apply to QueuePool (PostgreSQL); SQLite (CI) uses
# StaticPool which does not accept these arguments.
_async_engine_kwargs: dict = {"echo": False, "pool_pre_ping": True}
if _is_postgres:
    _async_engine_kwargs.update({"pool_size": 5, "max_overflow": 10})

async_engine = create_async_engine(DATABASE_URL, **_async_engine_kwargs)
AsyncSessionLocal = async_sessionmaker(async_engine, expire_on_commit=False)

# Sync engine — used by Celery workers only.
_sync_engine_kwargs: dict = {"pool_pre_ping": True}
if _is_postgres:
    _sync_engine_kwargs.update({"pool_size": 5, "max_overflow": 10})

sync_engine = create_engine(SYNC_DATABASE_URL, **_sync_engine_kwargs)
SyncSessionLocal = sessionmaker(bind=sync_engine, autocommit=False, autoflush=False)

async def get_db() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        yield session