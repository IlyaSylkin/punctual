.PHONY: install up down logs migrate migrate-down check lint format type test clean

install:          ## окружение и git-хуки
	uv sync
	uv run pre-commit install --hook-type pre-commit --hook-type commit-msg

up:               ## поднять хранилища и буфер
	docker compose up -d --wait

down:
	docker compose down

logs:
	docker compose logs -f

migrate:          ## применить миграции ClickHouse
	docker compose run --rm migrate up

migrate-down:     ## откатить последнюю миграцию
	docker compose run --rm migrate down 1

check: lint type test   ## всё, что проверяет CI

lint:
	uv run ruff check .
	uv run ruff format --check .

format:           ## исправить то, что исправляется автоматически
	uv run ruff check --fix .
	uv run ruff format .

type:
	uv run mypy

test:
	uv run pytest

clean:
	rm -rf .ruff_cache .mypy_cache .pytest_cache dist
