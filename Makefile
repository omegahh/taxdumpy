# Development commands. Production releases use the tag-triggered OIDC workflow.

.PHONY: help install test test-fast test-slow test-integration test-unit coverage coverage-xml lint format clean build upload-test ci-test ci-lint

help: ## Show available commands
	@awk 'BEGIN {FS = ":.*## "} /^[a-zA-Z_-]+:.*## / {printf "%-20s %s\n", $$1, $$2}' $(MAKEFILE_LIST)

install: ## Install development dependencies
	python -m pip install -e '.[dev]'

test: ## Run all tests with the coverage gate
	python -m pytest

test-fast: ## Skip slow and integration tests
	python -m pytest -m "not slow and not integration"

test-slow: ## Run slow tests
	python -m pytest -m slow

test-integration: ## Run integration tests
	python -m pytest -m integration

test-unit: ## Run unit and unmarked fast tests
	python -m pytest -m "unit or not (slow or integration)"

coverage: ## Generate HTML and terminal coverage reports
	python -m pytest --cov-report=html --cov-report=term-missing

coverage-xml: ## Generate XML coverage for CI
	python -m pytest --cov-report=xml

lint: ## Check formatting and import sorting
	ruff format --check src/ tests/ scripts/
	ruff check src/ tests/ scripts/

format: ## Format Python and sort imports
	ruff check src/ tests/ scripts/ --fix
	ruff format src/ tests/ scripts/

clean: ## Remove generated build and coverage artifacts
	rm -rf build/ dist/ htmlcov/
	rm -f coverage.xml .coverage
	find src tests scripts -type d -name __pycache__ -prune -exec rm -rf {} +

build: ## Build wheel and sdist without removing existing artifacts
	python -m build

upload-test: ## Prepare and upload to TestPyPI (requires VERSION)
	@test -n "$(VERSION)" || (echo 'Use make upload-test VERSION=1.4.0rc1'; exit 1)
	python scripts/release.py --version "$(VERSION)" --test-pypi

ci-test: coverage-xml ## Run CI tests

ci-lint: lint ## Run CI quality checks
