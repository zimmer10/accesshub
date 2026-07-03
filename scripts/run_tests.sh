#!/usr/bin/env bash
set -euo pipefail

# integration-тесты бьют по настоящему Postgres (отдельная БД accesshub_test,
# создаётся автоматически в tests/integration/conftest.py) — поднимаем db из
# того же compose-проекта и подключаем тестовый контейнер к его сети.
docker compose up -d db

docker run --rm \
  --network accesshub_default \
  -v "$(pwd)":/workspace \
  -w /workspace \
  -e JWT_SECRET_KEY="test-secret-for-local-runs" \
  -e ADMIN_DATABASE_URL="postgresql://accesshub:accesshub@db:5432/postgres" \
  -e TEST_DATABASE_URL="postgresql+asyncpg://accesshub:accesshub@db:5432/accesshub_test" \
  python:3.12-slim \
  bash -c "pip install --quiet -e .[dev] && pytest --cov=app --cov-report=term-missing"
