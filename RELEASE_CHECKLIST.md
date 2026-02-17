# Release Checklist

This checklist tracks repeatable release hygiene tasks for Tooli.

## Stabilization Gate

- [x] Repository hygiene pass completed (no accidental duplicate-suffix tracked files).
- [x] Version consistency pass completed (`pyproject.toml` version matches latest `CHANGELOG.md` entry).
- [x] Docs status markers are current in `PLAN.md` and `PRD.md`.
- [x] CI passes on supported Python versions.
- [x] Changelog entry drafted for the release.
- [x] Release workflow (`publish.yml`) reviewed before tagging.

## Pre-Tag Release Steps

1. Run `ruff check .` (new files should be clean).
2. Run `mypy tooli`.
3. Run `pytest tests` (259 tests passing as of v4.0.0).
4. Confirm `CHANGELOG.md` includes the target version and release date.
5. Confirm `pyproject.toml` version matches.
6. Confirm `tooli/__init__.py` `__version__` matches.

## Release Steps

1. Create a release branch: `git checkout -b release/vX.Y.Z`
2. Commit and push.
3. Create PR, merge to main.
4. Tag: `git tag vX.Y.Z && git push origin vX.Y.Z`
5. Create GitHub Release (triggers trusted publisher workflow to PyPI).
6. Verify package on PyPI: `pip install tooli==X.Y.Z`

## Release History

| Version | Date | Notes |
|---------|------|-------|
| 4.0.0 | 2026-02-17 | Agent Skill Platform |
| 3.0.0 | 2026-02-16 | Documentation workflow primitives |
| 2.0.0 | 2026-02-16 | Agent-Environment Interface |
| 1.0.0 | 2026-02-15 | Initial release |
