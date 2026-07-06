.PHONY: help install test test-all lint format check build clean pre-commit check-release-readiness

PYTHON ?= python3

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

install: ## Install package in development mode
	pip install -e ".[dev]"

test: ## Run test suite
	$(PYTHON) -m pytest tests/ -v --tb=short

test-all: ## Run test suite with coverage
	$(PYTHON) -m pytest tests/ -v --tb=short --cov=polymind --cov-report=term-missing

lint: ## Run ruff linter
	ruff check .

format: ## Format code with ruff
	ruff format .

check: lint test ## Run lint + test

build: clean ## Build source distribution and wheel
	$(PYTHON) -m build

clean: ## Clean build artifacts
	rm -rf dist/ build/ *.egg-info
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete

pre-commit: ## Run pre-commit on all files
	pre-commit run --all-files

.PHONY: check-release-readiness
check-release-readiness:
	@echo "=== Checking all public modules import ==="
	python -c "import polymind; print('polymind:', dir(polymind))"
	@echo "=== Running full test suite ==="
	python -m pytest tests/ -q --timeout=60
	@echo "=== Checking for NotImplementedError stubs ==="
	! grep -r "NotImplementedError" polymind/ --include="*.py" | grep -v "__pycache__" | grep -v ".pyc" || echo "WARNING: NotImplementedError stubs found"
	@echo "=== Verifying entry points ==="
	python -c "from polymind.cli.main import main; print('CLI entry point: OK')"
	@echo "=== Release readiness check complete ==="
