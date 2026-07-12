# Contributing to django-hostmap

Practical guide for contributors working on this package.

---

## Prerequisites

- Python 3.11 or later
- [uv](https://docs.astral.sh/uv/) (recommended) or pip
- Django 5.0 or later (installed as part of the dev setup)
- No database server is required: the test suite uses SQLite
  (adjust this line if the package tests against PostgreSQL)

---

## Local Development Setup

```bash
git clone https://github.com/icvoss/django-hostmap.git
cd django-hostmap

# Create a virtual environment
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate

# Install in editable mode with dev dependencies
pip install -e ".[dev]"
```

Or with uv:

```bash
uv venv && source .venv/bin/activate
uv pip install -e ".[dev]"
```

---

## Running Tests

```bash
pytest tests/ -v --tb=short
```

Test configuration lives in `[tool.pytest.ini_options]` in `pyproject.toml`,
so no environment variables are needed.

---

## Code Standards

All Python code is linted and formatted with [ruff](https://docs.astral.sh/ruff/),
configured in `pyproject.toml`.

| Setting | Value |
|---------|-------|
| Line length | 120 |
| Quote style | Double |
| Target Python | 3.11 |

```bash
# Check for lint errors
ruff check .

# Check formatting (no writes)
ruff format --check .

# Apply formatting
ruff format .
```

CI will fail if either check reports errors. Run both before pushing.

---

## Repository Structure

```
django-hostmap/
    src/hostmap/     # importable package
    tests/
        settings.py     # Django settings for the test suite
        conftest.py
        test_*.py
    pyproject.toml      # package metadata, dependencies, tool config
    CHANGELOG.md
    README.md
    RELEASING.md
```

---

## Git Workflow

### Commits

Use [Conventional Commits](https://www.conventionalcommits.org/):

```
<type>: <description>
```

| Type | When to use |
|------|-------------|
| `feat` | New feature or capability |
| `fix` | Bug fix |
| `chore` | Maintenance, version bumps, dependency updates |
| `docs` | Documentation only |
| `test` | Adding or updating tests |
| `style` | Formatting, whitespace, no logic change |
| `refactor` | Code change that is neither a fix nor a feature |

### Branches and PRs

Push feature branches and open a pull request against `main`. CI must pass
before merging. Prefer small, focused commits over large ones.

---

## Releasing

See [RELEASING.md](RELEASING.md) for the full release process. The short
version:

1. Bump the version in `pyproject.toml` and `src/hostmap/__init__.py`.
2. Update `CHANGELOG.md`: rename `[Unreleased]` to `[<version>] - <YYYY-MM-DD>`.
3. Open a PR, get it reviewed, and merge to `main`.
4. Tag the merged commit and push the tag:

   ```bash
   git tag v<version>
   git push origin v<version>
   ```

The tag push triggers the CI publish workflow automatically.
