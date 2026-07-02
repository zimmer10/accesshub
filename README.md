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

```bash
uv venv --python 3.12 .venv && source .venv/bin/activate
uv pip install -e ".[dev]"
pytest
```

## Статус проекта

Проект в разработке. Готово:

- Docker/Compose (app, db, redis, adminer), multi-stage Dockerfile, CI
  (lint + tests + docker build)
- модель данных (User/Group/Role/Permission/AuditLog, вложенные группы через
  `parent_group_id`), Alembic-миграции, seed-скрипт
- аутентификация: `POST /auth/register`, `/auth/login`, `/auth/refresh`
  (JWT access/refresh, bcrypt)

Дальше по плану: CRUD API (users/groups/roles/permissions), резолвер эффективных прав
(обход иерархии групп + кэш в Redis), audit log, веб-панель на Jinja2 + htmx.
