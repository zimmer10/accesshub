# AccessHub

RBAC-сервис управления доступами: REST API + веб-панель + БД. Централизованно решает
вопрос «может ли пользователь X делать Y с ресурсом Z» — с вложенными группами, ролями,
резолвингом эффективных прав и аудитом изменений.

## Стек

FastAPI · SQLAlchemy 2.0 (async) + Alembic · PostgreSQL 16 · Redis · JWT (PyJWT) + bcrypt ·
pytest · Docker / docker-compose

## Быстрый старт

```bash
cp .env.example .env   # и подставь свой JWT_SECRET_KEY
docker compose up --build
```

- API: http://localhost:8000
- Swagger UI: http://localhost:8000/docs
- Adminer (просмотр БД): http://localhost:8080

## Тесты

Integration-тесты бьют по настоящему Postgres (отдельная БД `accesshub_test`,
создаётся автоматически), поэтому перед запуском нужна поднятая `db`:

```bash
uv venv --python 3.12 .venv && source .venv/bin/activate
uv pip install -e ".[dev]"
docker compose up -d db
pytest --cov=app --cov-report=term-missing
```

Либо `make test` — гоняет тесты в одноразовом контейнере, подключённом к сети compose.

## Статус проекта

Проект в разработке. Готово:

- Docker/Compose (app, db, redis, adminer), multi-stage Dockerfile, CI
  (lint + tests + docker build)
- модель данных (User/Group/Role/Permission/AuditLog, вложенные группы через
  `parent_group_id`), Alembic-миграции, seed-скрипт
- аутентификация: `POST /auth/register`, `/auth/login`, `/auth/refresh`
  (JWT access/refresh, bcrypt)
- CRUD API: `/users`, `/groups` (+ members, + roles), `/roles` (+ permissions), `/permissions`,
  все под JWT-авторизацией (`get_current_user`)
- резолвер эффективных прав: обход иерархии групп вверх (BFS, устойчив к циклам),
  прямые + групповые роли, wildcard-права (`invoice:*`); `GET /access/check`,
  `GET /users/{id}/effective-permissions`
- защита от циклов в иерархии групп при смене родителя (`SELECT ... FOR UPDATE`
  на время проверки+записи — закрывает race condition при параллельных запросах)
- unit + integration тесты (httpx + реальный Postgres), покрытие ~93%

Дальше по плану: кэш резолва в Redis + инвалидация, audit log, веб-панель на Jinja2 + htmx.
