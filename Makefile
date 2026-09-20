.PHONY: install check lint format type test clean

install:          ## окружение и git-хуки
	uv sync
	uv run pre-commit install --hook-type pre-commit --hook-type commit-msg

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
