import os
import pytest
import uuid
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.dialects.postgresql import JSONB, UUID

# Provide a stable Fernet key for the test suite so encrypt/decrypt calls in
# the routers don't raise RuntimeError due to a missing env var.
os.environ.setdefault(
    "FIELD_ENCRYPTION_KEY",
    # 32 zero bytes, URL-safe base64. Valid Fernet key; NOT for production use.
    "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=",
)

from backend.main import app
from backend.database import get_db, Base
from backend.routers.user import get_current_user, get_current_user_id, AuthenticatedUser

# --- SQLITE COMPILER OVERRIDES ---
# Teach SQLite how to handle Postgres-specific data types during tests
@compiles(JSONB, "sqlite")
def compile_jsonb_sqlite(type_, compiler, **kw):
    return "JSON"

@compiles(UUID, "sqlite")
def compile_uuid_sqlite(type_, compiler, **kw):
    return "VARCHAR"
# ---------------------------------

# 1. The Test Database
# We create a completely separate, in-memory SQLite database just for testing
# This means tests run in milliseconds and never touch the real PostgreSQL data
# Note: SQLite is fine here, but in strict enterprise setups, we'd use a temporary Postgres instance
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

test_engine = create_async_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = async_sessionmaker(test_engine, expire_on_commit = False, class_ = AsyncSession)

# 2. The Fixtures

@pytest.fixture(scope="session", autouse=True)
async def setup_test_db():
    """Creates all database tables in memory before the test suite starts"""
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

@pytest.fixture
async def db_session():
    """
    Yields a fresh database session for every single test.
    This guarantees State Isolation. Test A cannot break Test B.
    """
    async with TestingSessionLocal() as session:
        yield session
        # We explicitly rollback after the test finishes to clear any saved data
        await session.rollback()

@pytest.fixture
def override_get_db(db_session):
    """A helper to override FastAPI's get_db dependency"""
    async def _get_db_override():
        yield db_session
    return _get_db_override

@pytest.fixture
def mock_user_id():
    """A hardcoded UUID for our 'test user'"""
    return str(uuid.uuid4())

@pytest.fixture
def override_get_user(mock_user_id):
    """A helper to bypass Supabase JWT validation entirely."""
    def _get_current_user_override():
        return AuthenticatedUser(user_id=mock_user_id, email="test@example.com")
    return _get_current_user_override

@pytest.fixture
def override_get_user_id(mock_user_id):
    """String-form user id for routes that depend on get_current_user_id."""
    def _get_current_user_id_override():
        return mock_user_id
    return _get_current_user_id_override

@pytest.fixture
async def client(override_get_db, override_get_user, override_get_user_id):
    """
    The ultimate TestClient.
    We intercept the app and inject our fake DB and fake User Auth.
    """
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user_id] = override_get_user_id
    app.dependency_overrides[get_current_user] = override_get_user
    
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
    
    # Clean up overrides after test
    app.dependency_overrides.clear()
