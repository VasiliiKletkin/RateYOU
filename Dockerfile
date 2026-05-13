FROM python:3.13-slim AS base

WORKDIR /app

ENV POETRY_VERSION=2.2.1 \
    POETRY_VIRTUALENVS_CREATE=false \
    POETRY_NO_INTERACTION=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

RUN pip install --no-cache-dir poetry==${POETRY_VERSION}

COPY pyproject.toml poetry.lock ./

# ─── dev ──────────────────────────────────────────────────────────────────────
# Includes dev-only tools (pytest, ruff, mypy, faker) and tests/. Consumed by
# the `dev` service in docker-compose.yml — Makefile targets shell into it via
# `docker compose run --rm dev <command>`.
FROM base AS dev

RUN poetry install --no-root --no-cache --with dev

COPY src/ ./src/
COPY tests/ ./tests/
COPY migrations/ ./migrations/
COPY locales/ ./locales/
COPY scripts/ ./scripts/
COPY alembic.ini ./

RUN pybabel compile -d locales

CMD ["python", "-m", "src.presentation.bot.main"]

# ─── prod ─────────────────────────────────────────────────────────────────────
# Last stage = the default target when `target:` isn't set, so the existing
# bot/admin/migrate services keep building this image without changes.
FROM base AS prod

RUN poetry install --no-root --no-cache --only=main

COPY src/ ./src/
COPY migrations/ ./migrations/
COPY locales/ ./locales/
COPY alembic.ini ./

RUN pybabel compile -d locales

CMD ["python", "-m", "src.presentation.bot.main"]
