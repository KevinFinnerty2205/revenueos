from __future__ import annotations

from collections.abc import AsyncIterator
from uuid import UUID

from fastapi import Request
from sqlalchemy import event, text
from sqlalchemy.engine.interfaces import DBAPIConnection
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import ConnectionPoolEntry

from revenueos.config import Settings
from revenueos.errors import PublicAPIError


def create_engine(settings: Settings) -> AsyncEngine | None:
    if settings.database_url is None:
        return None
    connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
    engine = create_async_engine(
        settings.database_url,
        echo=False,
        pool_pre_ping=True,
        connect_args=connect_args,
    )
    if settings.database_url.startswith("sqlite"):
        event.listen(engine.sync_engine, "connect", _enable_sqlite_foreign_keys)
    return engine


def _enable_sqlite_foreign_keys(
    connection: DBAPIConnection,
    connection_record: ConnectionPoolEntry,
) -> None:
    del connection_record
    cursor = connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


def create_session_factory(engine: AsyncEngine | None) -> async_sessionmaker[AsyncSession] | None:
    if engine is None:
        return None
    return async_sessionmaker(engine, expire_on_commit=False, autoflush=False)


async def get_db(request: Request) -> AsyncIterator[AsyncSession]:
    session_factory: async_sessionmaker[AsyncSession] | None = request.app.state.session_factory
    if session_factory is None:
        raise PublicAPIError(
            "persistence_unavailable",
            "Persistence is not configured for this environment.",
            status_code=503,
        )
    async with session_factory() as session:
        yield session


async def database_is_ready(engine: AsyncEngine | None) -> bool:
    if engine is None:
        return False
    try:
        async with engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
    except (OSError, SQLAlchemyError):
        return False
    return True


async def set_tenant_database_context(session: AsyncSession, organisation_id: UUID) -> None:
    """Set the transaction-local PostgreSQL RLS context from trusted auth."""

    bind = session.get_bind()
    if bind.dialect.name == "postgresql":
        await session.execute(
            text("SELECT set_config('app.organisation_id', :organisation_id, true)"),
            {"organisation_id": str(organisation_id)},
        )
