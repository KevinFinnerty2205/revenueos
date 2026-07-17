from __future__ import annotations

import asyncio
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import create_async_engine

from revenueos.config import Settings
from revenueos.main import create_app
from revenueos.models import Base

TEST_DB = Path(__file__).with_name("test_revenueos.db")
TEST_DB_URL = f"sqlite+aiosqlite:///{TEST_DB}"


@pytest.fixture(scope="session", autouse=True)
def database() -> Iterator[None]:
    if TEST_DB.exists():
        TEST_DB.unlink()
    engine = create_async_engine(TEST_DB_URL, connect_args={"check_same_thread": False})

    async def create_tables() -> None:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

    async def dispose() -> None:
        await engine.dispose()
        if TEST_DB.exists():
            TEST_DB.unlink()

    asyncio.run(create_tables())
    yield
    asyncio.run(dispose())


@pytest.fixture
def app() -> FastAPI:
    return create_app(
        Settings(
            environment="test",
            auth_mode="mock",
            mock_auth_enabled=True,
            database_url=TEST_DB_URL,
            log_level="WARNING",
            cors_origins="http://localhost:3000",
        ),
    )


@pytest.fixture
def client(app: FastAPI) -> Iterator[TestClient]:
    with TestClient(app) as test_client:
        yield test_client
