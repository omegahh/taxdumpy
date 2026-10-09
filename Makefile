# Makefile for taxdumpy development

.PHONY: help install test test-fast test-slow test-integration coverage lint format clean build upload docs

help: ## Show this help message
	@echo "Available commands:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

install: ## Install package in development mode
	pip install -e .[dev]

test: ## Run all tests
	pytest

test-fast: ## Run only fast tests (skip slow/integration tests)
	pytest -m "not slow and not integration"

test-slow: ## Run only slow tests
	pytest -m "slow"

test-integration: ## Run only integration tests
	pytest -m "integration"

test-unit: ## Run only unit tests
	pytest -m "unit or not (slow or integration)"

coverage: ## Run tests with coverage report
	pytest --cov=taxdumpy --cov-report=html --cov-report=term-missing

coverage-xml: ## Generate XML coverage report for CI
	pytest --cov=taxdumpy --cov-report=xml

lint: ## Run code linting
	ruff format --check src/ tests/
	ruff check src/ tests/
	@echo "✓ Code formatting check passed"

format: ## Format code and sort imports with ruff
	ruff check src/ tests/ --fix
	ruff format src/ tests/
	@echo "✓ Code formatted"

clean: ## Clean build artifacts
	rm -rf build/
	rm -rf dist/
	rm -rf *.egg-info/
	rm -rf htmlcov/
	rm -f coverage.xml
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete

build: clean ## Build package
	python -m build

upload: build ## Upload package to PyPI (requires authentication)
	python -m twine upload dist/*

upload-test: build ## Upload package to Test PyPI
	python -m twine upload --repository testpypi dist/*

docs: ## Generate documentation (placeholder)
	@echo "Documentation generation not yet implemented"

# Development helpers
dev-install: ## Install in development mode with all dependencies
	pip install -e .[dev]

dev-test: ## Run development test suite
	pytest -v --tb=short

dev-coverage: ## Run coverage and open HTML report
	pytest --cov=taxdumpy --cov-report=html
	@echo "Opening coverage report..."
	@which open >/dev/null && open htmlcov/index.html || echo "Open htmlcov/index.html in your browser"

# CI/CD helpers
ci-test: ## Run tests suitable for CI
	pytest --cov=taxdumpy --cov-report=xml --cov-fail-under=80

ci-lint: ## Run linting for CI
	ruff format --check --diff src/ tests/
	ruff check src/ tests/

# Sample data helpers
create-sample-data: ## Create minimal sample taxdump data for testing
	@echo "Creating sample taxdump data..."
	mkdir -p sample_data
	@echo "Sample data creation not yet implemented"
