# Release Checklist

This checklist tracks repeatable release hygiene tasks for Tooli, starting with the v1.1 stabilization program.

## v1.1 Stabilization Gate

- [ ] Repository hygiene pass completed (no accidental duplicate-suffix tracked files).
- [ ] Version consistency pass completed (`pyproject.toml` version matches latest `CHANGELOG.md` entry).
- [ ] Docs status markers are current in `PLAN.md` and `PRD.md`.
- [ ] CI passes on supported Python versions.
- [ ] Changelog entry drafted for the release candidate.
- [ ] Release workflow (`publish.yml`) reviewed before tagging.

## Pre-Tag Release Steps

1. Run `python scripts/check_v11_hardening.py`.
2. Run `ruff check .`.
3. Run `mypy tooli`.
4. Run `pytest tests`.
5. Confirm `CHANGELOG.md` includes the target version and release date.
