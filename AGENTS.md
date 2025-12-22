# Repository Guidelines

## Project Structure & Module Organization
- `kunit/cli.py` — Click-based CLI entry point.
- `kunit/core/` — fixed-width parsing/formatting and unit math (`engine.py`, `fixed.py`, `units.py`).
- `kunit/models/` — LS-DYNA keyword specs (e.g., `eos_gruneisen.py`, `eos_jwl.py`, `mat_johnson_cook.py`).
- `.k` files — LS-DYNA inputs/outputs; examples: `materials.k`, `kunit/materials.k`, `out.k`.

## Build, Test, and Development Commands
- Run CLI help: `python -m kunit.cli --help`
- List models: `python -m kunit.cli list-models`
- Convert example: `python -m kunit.cli convert materials.k --src mm-mg-us --dst m-kg-s -o out.k`
- Dev setup (example): `python -m venv .venv && . .venv/bin/activate && pip install -U pip click pytest`

## Coding Style & Naming Conventions
- Python 3.11+ with type hints; 4-space indentation.
- Names: modules/functions `snake_case`, classes `CapWords`, constants `UPPER_SNAKE`.
- Preserve fixed-width format: 8 fields × 10 chars per line (see `kunit/core/fixed.py`). Do not reflow whitespace.
- Keep core logic pure and side-effect free; perform I/O only in `cli.py`.
- Formatting/linting: prefer `black` and `ruff` if available; otherwise match existing style.

## Testing Guidelines
- Framework: `pytest`. Place tests under `tests/` as `test_*.py`.
- Cover: `convert_text`, `convert_block`, numeric formatting (`format_lsdyna_10`), and each model spec’s dims/cards.
- Run: `pytest -q` (optionally `pytest --maxfail=1 -q`). Add sample `.k` snippets to fixtures.

## Runtime Verification
- Before modifying any files, start the web application inside a container to confirm it boots cleanly.
- Preferred command (stop with Ctrl+C after successful startup): `uv run gunicorn -c gunicorn.conf.py kunit.web.app:app`.
## Commit & Pull Request Guidelines
- Commit messages: follow Conventional Commits (e.g., `feat(core): add scale factor for pressure`).
- PRs must include: clear description, linked issue (if any), before/after `.k` line examples, and tests for conversion changes.
- Verify locally with at least one `--src/--dst` pair covering modified dims.

## Security & Configuration Tips
- Never modify comment/keyword lines or field widths; only replace numeric fields.
- Validate model names via `python -m kunit.cli list-models` and prefer explicit `--models` when changing behavior.

