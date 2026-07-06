# Release Process

## Prerequisites

- All changes merged to `main`
- CI green on `main`
- Local `main` branch up to date

## Release Checklist

### 1. Version Bump
- [ ] Update version in `pyproject.toml`
- [ ] Update `CHANGELOG.md` with release date
- [ ] Commit: `bump version to X.Y.Z`

### 2. Readiness Checks (`make check-release-readiness`)
- [ ] All public modules pass import: `python -c "import polymind; ..."` [auto]
- [ ] Full test suite passes: `pytest tests/ -q` [auto]
- [ ] No NotImplementedError stubs in exposed API surface [auto]
- [ ] pyproject.toml entry points match implemented modules [auto]

### 3. Build & Verify
- [ ] `make build` succeeds
- [ ] `make build-verify` passes (wheel metadata, install, import)

### 4. PyPI Publish
- [ ] `make publish` to TestPyPI
- [ ] Verify TestPyPI install in clean environment
- [ ] `make publish` to PyPI
- [ ] Tag release: `git tag vX.Y.Z && git push --tags`

## Automation
Run `make check-release-readiness` before any release to auto-verify steps in section 2.
