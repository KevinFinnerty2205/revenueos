FROM ghcr.io/astral-sh/uv:0.12.12 AS uv

FROM python:3.12-slim-bookworm AS pgdg

RUN apt-get update \
    && apt-get install --yes --no-install-recommends ca-certificates curl \
    && install -d -m 0755 /etc/apt/keyrings \
    && curl --fail --show-error --silent \
      https://www.postgresql.org/media/keys/ACCC4CF8.asc \
      --output /etc/apt/keyrings/postgresql.asc \
    && echo "0144068502a1eddd2a0280ede10ef607d1ec592ce819940991203941564e8e76  /etc/apt/keyrings/postgresql.asc" \
      | sha256sum --check --strict - \
    && echo "deb [signed-by=/etc/apt/keyrings/postgresql.asc] https://apt.postgresql.org/pub/repos/apt bookworm-pgdg main" \
      > /etc/apt/sources.list.d/pgdg.list

FROM python:3.12-slim-bookworm AS build

ENV UV_COMPILE_BYTECODE=1
ENV UV_LINK_MODE=copy
ENV UV_PYTHON_DOWNLOADS=0
COPY --from=uv /uv /uvx /bin/
WORKDIR /app
COPY apps/api/pyproject.toml apps/api/uv.lock ./
COPY apps/api/src src
RUN uv sync --locked --no-dev --no-editable --no-cache

FROM python:3.12-slim-bookworm AS runtime

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PATH=/app/.venv/bin:$PATH
WORKDIR /app
COPY --from=pgdg /etc/apt/keyrings/postgresql.asc /etc/apt/keyrings/postgresql.asc
COPY --from=pgdg /etc/apt/sources.list.d/pgdg.list /etc/apt/sources.list.d/pgdg.list
RUN apt-get update \
    && apt-get install --yes --no-install-recommends postgresql-client-16 ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && addgroup --system --gid 1001 revenueos \
    && adduser --system --uid 1001 --ingroup revenueos revenueos
COPY --from=build --chown=revenueos:revenueos /app/.venv /app/.venv
COPY --chown=revenueos:revenueos apps/api/alembic.ini ./alembic.ini
COPY --chown=revenueos:revenueos apps/api/alembic ./alembic

USER revenueos
EXPOSE 8080 8081
CMD ["uvicorn", "revenueos.main:app", "--host", "0.0.0.0", "--port", "8080", "--no-proxy-headers"]
