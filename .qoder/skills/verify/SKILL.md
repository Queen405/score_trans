---
name: verify
description: Run format check, lint, typecheck, and tests to verify the codebase is in good shape. Use after making changes or before committing.
---

# Verify Skill

Run the full verification pipeline for the Score Trans project. Execute steps in order; stop and report if any step fails.

## Steps

### 1. Format and lint (Python backend)

```bash
.venv/Scripts/python.exe -m ruff format --check backend/ tests/
.venv/Scripts/python.exe -m ruff check backend/ tests/
```

If format check fails, run with `--diff` to show what needs fixing. Do NOT auto-fix — report to the user.

### 2. Typecheck (Frontend)

```bash
cd desktop && npx vue-tsc --noEmit
```

### 3. Backend tests

```bash
.venv/Scripts/python.exe -m pytest
```

If only specific areas changed, run the relevant targeted test:
- Changed `services/render/` → `python -m pytest tests/test_render.py`
- Changed architecture/imports → `python -m pytest tests/test_architecture.py`

## Report

Summarize results as:
- ✅ / ❌ for each step
- If any step failed, show the error output and suggest a fix
