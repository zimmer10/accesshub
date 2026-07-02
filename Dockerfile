# --- builder: ставим зависимости и собираем пакет ---
FROM python:3.12-slim AS builder

WORKDIR /build

RUN pip install --no-cache-dir --upgrade pip

COPY pyproject.toml .
COPY app ./app

RUN pip install --no-cache-dir --prefix=/install .

# --- runtime: только то, что нужно, чтобы запустить приложение ---
FROM python:3.12-slim AS runtime

RUN useradd --create-home --shell /bin/bash appuser

WORKDIR /app

COPY --from=builder /install /usr/local
COPY alembic.ini .
COPY migrations ./migrations
COPY scripts ./scripts
RUN chmod +x scripts/entrypoint.sh scripts/wait-for-db.sh

USER appuser

EXPOSE 8000

ENTRYPOINT ["./scripts/entrypoint.sh"]
