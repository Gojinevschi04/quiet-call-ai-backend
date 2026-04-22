FROM python:3.13-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update && \
    apt-get install -y --no-install-recommends gcc libpq-dev && \
    rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir poetry==2.1.3 && \
    poetry config virtualenvs.create false

COPY pyproject.toml poetry.lock ./
RUN poetry install --only main --no-interaction --no-ansi

COPY . .

RUN mkdir -p /app/storage

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--no-server-header"]

# --- Test stage: includes dev dependencies (pytest, ruff, mypy, etc.) ---
FROM base AS test

ENV RATE_LIMIT_PER_MINUTE=0

# Install dev dependencies on top of main deps
RUN poetry install --with dev --no-interaction --no-ansi || pip install pytest pytest-asyncio pytest-cov httpx

COPY . .

CMD ["python", "-m", "pytest", "--tb=short", "-v"]
