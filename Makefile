.PHONY: up down build logs migrate seed test

up:
	docker compose up --build

down:
	docker compose down

build:
	docker compose build

logs:
	docker compose logs -f

migrate:
	docker compose exec app alembic upgrade head

seed:
	./scripts/seed_data.sh

test:
	./scripts/run_tests.sh
