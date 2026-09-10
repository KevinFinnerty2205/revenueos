from __future__ import annotations

import asyncio
import base64
import binascii
import os
import ssl
from logging.config import fileConfig

from alembic import context
from dotenv import load_dotenv
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from revenueos.models import Base

config = context.config
load_dotenv()
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def get_database_url() -> str:
    return os.getenv("DATABASE_URL", config.get_main_option("sqlalchemy.url"))


def run_migrations_offline() -> None:
    context.configure(
        url=get_database_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata, compare_type=True)
    with context.begin_transaction():
        context.run_migrations()


def database_connect_args() -> dict[str, object]:
    mode = os.getenv("API_DATABASE_TLS_MODE", "disable")
    if mode == "disable":
        return {}
    if mode not in {"verify_full_system", "verify_full_custom_ca"}:
        raise RuntimeError("API_DATABASE_TLS_MODE is invalid.")
    tls_context = ssl.create_default_context(ssl.Purpose.SERVER_AUTH)
    if mode == "verify_full_custom_ca":
        encoded = os.getenv("API_DATABASE_CA_CERTIFICATE_BASE64")
        if not encoded:
            raise RuntimeError("API_DATABASE_CA_CERTIFICATE_BASE64 is required for custom-CA TLS.")
        try:
            certificate = base64.b64decode(encoded, validate=True).decode("ascii")
            tls_context.load_verify_locations(cadata=certificate)
        except (binascii.Error, ValueError, UnicodeDecodeError, ssl.SSLError) as exc:
            raise RuntimeError("The database CA certificate is invalid.") from exc
    tls_context.check_hostname = True
    tls_context.verify_mode = ssl.CERT_REQUIRED
    return {"ssl": tls_context}


async def run_async_migrations() -> None:
    configuration = config.get_section(config.config_ini_section, {})
    configuration["sqlalchemy.url"] = get_database_url()
    connectable = async_engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
        connect_args=database_connect_args(),
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
