import os
from collections.abc import AsyncIterator, Awaitable, Callable

import asyncpg
import pytest_asyncio
import redis.asyncio as redis
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.cache import get_redis
from app.core.db import get_db
from app.core.security import create_access_token, hash_password
from app.main import app
from app.models import Base, User

# Отдельная тестовая БД на том же Postgres, что и dev/seed — чтобы тесты
# никогда не трогали данные из docker-compose/seed_data.sh.
ADMIN_DATABASE_URL = os.environ.get(
    "ADMIN_DATABASE_URL", "postgresql://accesshub:accesshub@localhost:5432/postgres"
)
TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL", "postgresql+asyncpg://accesshub:accesshub@localhost:5432/accesshub_test"
)
TEST_DB_NAME = TEST_DATABASE_URL.rsplit("/", 1)[-1]

# Отдельный номер логической БД в Redis (по умолчанию 1, а не 0) — чтобы не
# пересекаться с тем, что могло бы там лежать из обычного docker-compose up.
TEST_REDIS_URL = os.environ.get("TEST_REDIS_URL", "redis://localhost:6379/1")

engine = create_async_engine(TEST_DATABASE_URL)
redis_pool = redis.ConnectionPool.from_url(TEST_REDIS_URL, decode_responses=True)


async def _ensure_test_database_exists() -> None:
    conn = await asyncpg.connect(ADMIN_DATABASE_URL)
    try:
        exists = await conn.fetchval("SELECT 1 FROM pg_database WHERE datname = $1", TEST_DB_NAME)
        if not exists:
            await conn.execute(f'CREATE DATABASE "{TEST_DB_NAME}"')
    finally:
        await conn.close()


@pytest_asyncio.fixture(scope="session", autouse=True)
async def _schema() -> AsyncIterator[None]:
    await _ensure_test_database_exists()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session() -> AsyncIterator[AsyncSession]:
    """Каждый тест выполняется в своей транзакции с SAVEPOINT'ами и откатывается
    целиком в конце — commit() внутри роутеров не фиксирует данные по-настоящему,
    так что тесты не оставляют следов и не мешают друг другу."""
    async with engine.connect() as conn:
        await conn.begin()
        session_factory = async_sessionmaker(
            bind=conn, expire_on_commit=False, join_transaction_mode="create_savepoint"
        )
        async with session_factory() as session:
            yield session
        await conn.rollback()


@pytest_asyncio.fixture
async def redis_client() -> AsyncIterator[redis.Redis]:
    client = redis.Redis(connection_pool=redis_pool)
    await client.flushdb()  # чистое состояние на каждый тест, независимо от прошлых
    try:
        yield client
    finally:
        await client.aclose()


@pytest_asyncio.fixture
async def client(db_session: AsyncSession, redis_client: redis.Redis) -> AsyncIterator[AsyncClient]:
    async def override_get_db() -> AsyncIterator[AsyncSession]:
        yield db_session

    async def override_get_redis() -> AsyncIterator[redis.Redis]:
        yield redis_client

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_redis] = override_get_redis
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def make_user(db_session: AsyncSession) -> Callable[..., Awaitable[User]]:
    counter = {"n": 0}

    async def _make_user(
        username: str | None = None,
        email: str | None = None,
        password: str = "password123",
    ) -> User:
        counter["n"] += 1
        username = username or f"user{counter['n']}"
        email = email or f"user{counter['n']}@example.com"
        user = User(username=username, email=email, hashed_password=hash_password(password))
        db_session.add(user)
        await db_session.flush()
        return user

    return _make_user


@pytest_asyncio.fixture
async def auth_headers(make_user: Callable[..., Awaitable[User]]) -> dict[str, str]:
    user = await make_user()
    token = create_access_token(user.id)
    return {"Authorization": f"Bearer {token}"}
