import pytest
import asyncio
from typing import AsyncGenerator
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from app.db.session import Base, get_db
from app.main import app

# Use SQLite for testing to avoid needing Postgres running
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

engine = create_async_engine(TEST_DATABASE_URL, echo=False)
TestingSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

# Monkeypatch JSONB for SQLite
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.types import JSON
import sqlalchemy.dialects.sqlite

def visit_JSONB(self, type_, **kw):
    return "JSON"

sqlalchemy.dialects.sqlite.base.SQLiteTypeCompiler.visit_JSONB = visit_JSONB



@pytest.fixture(scope="function")
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with TestingSessionLocal() as session:
        yield session

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

@pytest.fixture(scope="function")
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()
