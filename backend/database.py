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
SYNC_DATABASE_URL = DATABASE_URL.replace("postgresql+asyncpg://", "postgresql+psycopg2://")

# Async engine — used by FastAPI
async_engine = create_async_engine(DATABASE_URL, echo=False)
AsyncSessionLocal = async_sessionmaker(async_engine, expire_on_commit=False)

# Sync engine — used by Celery workers only
sync_engine = create_engine(SYNC_DATABASE_URL)
SyncSessionLocal = sessionmaker(bind=sync_engine, autocommit=False, autoflush=False)

async def get_db() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        yield session