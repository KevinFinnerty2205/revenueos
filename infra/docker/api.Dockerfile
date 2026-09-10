FROM ghcr.io/astral-sh/uv:0.12.12 AS uv

FROM python:3.12-slim AS build

ENV UV_COMPILE_BYTECODE=1
ENV UV_LINK_MODE=copy
ENV UV_PYTHON_DOWNLOADS=0
COPY --from=uv /uv /uvx /bin/
WORKDIR /app
COPY apps/api/pyproject.toml apps/api/uv.lock apps/api/README.md ./
COPY apps/api/src src
RUN uv sync --locked --no-dev --no-editable --no-cache

FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PATH=/app/.venv/bin:$PATH
WORKDIR /app
RUN apt-get update \
    && apt-get install --yes --no-install-recommends postgresql-client ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && addgroup --system --gid 1001 revenueos \
    && adduser --system --uid 1001 --ingroup revenueos revenueos
COPY --from=build --chown=revenueos:revenueos /app/.venv /app/.venv
COPY --chown=revenueos:revenueos apps/api/alembic.ini ./alembic.ini
COPY --chown=revenueos:revenueos apps/api/alembic ./alembic

USER revenueos
EXPOSE 8080 8081
CMD ["uvicorn", "revenueos.main:app", "--host", "0.0.0.0", "--port", "8080", "--proxy-headers", "--forwarded-allow-ips", "*"]
