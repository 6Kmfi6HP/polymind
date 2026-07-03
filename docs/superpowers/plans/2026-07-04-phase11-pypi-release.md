# Phase 11: PyPI Release Readiness — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Prepare Polymind for PyPI publication with Makefile, pre-commit hooks, and verified build.

**Architecture:** New developer tooling files (Makefile, .pre-commit-config.yaml, MANIFEST.in) plus pyproject.toml metadata updates.

**Tech Stack:** Python 3.10+, make, pre-commit, ruff, build

## Global Constraints

- All existing tests must continue to pass
- No new runtime dependencies
- Makefile targets must be self-documenting (output help text)
- Pre-commit hooks must not modify source code without tracking

---

### Task 1: Makefile

**Files:**
- Create: `Makefile`

- [ ] **Step 1: Create Makefile**

```makefile
.PHONY: help install test lint format build clean

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

install: ## Install package in development mode
	pip install -e ".[dev]"

test: ## Run test suite
	python -m pytest tests/ -v --tb=short

test-all: ## Run test suite with coverage
	python -m pytest tests/ -v --tb=short --cov=polymind --cov-report=term-missing

lint: ## Run ruff linter
	ruff check .

format: ## Format code with ruff
	ruff format .

check: lint test ## Run lint + test

build: clean ## Build source distribution and wheel
	python -m build

clean: ## Clean build artifacts
	rm -rf dist/ build/ *.egg-info
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete

pre-commit: ## Run pre-commit on all files
	pre-commit run --all-files
```

- [ ] **Step 2: Verify Makefile works**

```bash
make help
make test
make lint
```

Expected: All targets work without error

- [ ] **Step 3: Commit**

```bash
git add Makefile
git commit -m "chore: add Makefile with developer task automation"
```

---

### Task 2: Pre-commit Hooks

**Files:**
- Create: `.pre-commit-config.yaml`

- [ ] **Step 1: Create pre-commit config**

```yaml
repos:
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v4.6.0
    hooks:
      - id: trailing-whitespace
      - id: end-of-file-fixer
      - id: check-yaml
      - id: check-json
      - id: check-toml

  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.5.0
    hooks:
      - id: ruff
        args: [--fix]
      - id: ruff-format
```

- [ ] **Step 2: Install and verify**

```bash
pip install pre-commit
pre-commit install
pre-commit run --all-files
```

Expected: All hooks pass (may have minor formatting fixes)

- [ ] **Step 3: Commit**

```bash
git add .pre-commit-config.yaml
git commit -m "chore: add pre-commit hook configuration"
```

---

### Task 3: Pyproject.toml Metadata & Build Verification

**Files:**
- Modify: `pyproject.toml`
- Create: `MANIFEST.in`

- [ ] **Step 1: Add missing PyPI fields to pyproject.toml**

Read the current pyproject.toml and ensure these fields are present:
- `[project.urls]` with Homepage, Repository, Documentation, Issues
- `[project.scripts]` with `polymind = "polymind.cli.main:main"`
- `long_description` from README.md
- `long_description_content_type = "text/markdown"`

- [ ] **Step 2: Create MANIFEST.in**

```
include README.md
include LICENSE
include pyproject.toml
recursive-include docs/ *.md
```

- [ ] **Step 3: Verify build**

```bash
pip install build
python -m build
```

Expected: dist/ contains .tar.gz and .whl

- [ ] **Step 4: Verify wheel install**

```bash
pip install dist/polymind-*.whl
polymind --help
```

Expected: Installs and help text shows

- [ ] **Step 5: Run tests after build verification**

```bash
python -m pytest tests/ -x --tb=short
```

Expected: ALL PASS (831+)

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml MANIFEST.in
git commit -m "chore: add PyPI metadata and build configuration"
```

---

### Task 4: Full Integration Verification

- [ ] **Step 1: Run complete test suite**

```bash
python -m pytest tests/ -x --tb=short
```

Expected: ALL PASS

- [ ] **Step 2: Verify CLI entry point**

```bash
polymind --help
polymind strategies
polymind report --help
```

Expected: All commands work

- [ ] **Step 3: Push**

```bash
git push origin integration-tests
```
