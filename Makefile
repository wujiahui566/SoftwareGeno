PYTHON ?= python3.12
VENV ?= .venv
BIN := $(VENV)/bin

.PHONY: install format format-check lint typecheck test test-integration integration check compose-validate mongo-up mongo-down clean

install:
	$(PYTHON) -m venv $(VENV)
	$(BIN)/python -m pip install --upgrade pip
	$(BIN)/python -m pip install --editable '.[dev]'

format:
	$(BIN)/ruff format .
	$(BIN)/ruff check --fix .

format-check:
	$(BIN)/ruff format --check .

lint:
	$(BIN)/ruff check .

typecheck:
	$(BIN)/mypy

test:
	$(BIN)/pytest

test-integration:
	$(BIN)/pytest -m integration

integration: mongo-up test-integration

compose-validate:
	docker compose --file docker-compose.yml config --quiet

check: format-check lint typecheck test compose-validate

mongo-up:
	docker compose --file docker-compose.yml up --detach --wait mongodb

mongo-down:
	docker compose --file docker-compose.yml down

clean:
	rm -rf build dist .pytest_cache .mypy_cache .ruff_cache
