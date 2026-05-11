FROM python:3.13-slim

WORKDIR /app

ENV POETRY_VERSION=2.2.1 \
    POETRY_VIRTUALENVS_CREATE=false \
    POETRY_NO_INTERACTION=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

RUN pip install --no-cache-dir poetry==${POETRY_VERSION}

COPY pyproject.toml poetry.lock ./
RUN poetry install --no-root --no-cache --only=main

COPY src/ ./src/
COPY migrations/ ./migrations/
COPY locales/ ./locales/
COPY alembic.ini ./

# Compile .po → .mo so the bot has translations at runtime.
RUN pybabel compile -d locales

# Overridden per service in docker-compose.yml
CMD ["python", "-m", "src.presentation.bot.main"]
