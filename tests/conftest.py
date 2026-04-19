"""Shared pytest fixtures for Articulate backend tests."""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from backend.api.questions import router as questions_router
from backend.api.system import router as system_router
from backend.database import get_db
from backend.models import Base

TEST_DB_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture
async def db_session():
    """In-memory SQLite session; schema created fresh per test."""
    engine = create_async_engine(TEST_DB_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        yield session
    await engine.dispose()


@pytest.fixture
async def api_client(db_session: AsyncSession):
    """Async HTTPX client wired to a minimal test FastAPI app with overridden DB."""
    test_app = FastAPI()
    test_app.include_router(questions_router)
    test_app.include_router(system_router)

    async def override_db():
        yield db_session

    test_app.dependency_overrides[get_db] = override_db

    async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
        yield client
