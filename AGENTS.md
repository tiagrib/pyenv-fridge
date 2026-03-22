# AI Agent Guide for pyenv-fridge

## What is this project?

**pyenv-fridge** is a CLI tool that backs up and restores Python virtual environments managed by `pyenv`. It captures environment snapshots (name, Python version, installed packages) as JSON files and supports restoring, diffing, and listing them. Snapshots can be stored in a cloud-synced directory for cross-machine portability.

Entry point: `fridge` CLI (defined in `pyproject.toml` as `pyenv_fridge.cli:main`).

## Repository structure

```
pyenv_fridge/              # Main package
├── __init__.py            # Package version (__version__)
├── cli.py                 # argparse CLI — subcommand handlers + parser
├── config.py              # FridgeConfig — OS-aware paths, persistence to config.json
├── fridge.py              # Fridge class — core logic: backup, restore, diff, list
├── models.py              # Data classes: EnvBackup, PackageInfo, EnvDiff, PackageDiff
├── backends/              # Virtualenv backend abstraction
│   ├── __init__.py        # get_backend() factory + _REGISTRY dict
│   ├── base.py            # VirtualenvBackend ABC
│   ├── pyenv_venv_win.py  # Windows backend (pyenv-win-venv)
│   └── pyenv_virtualenv.py# Linux/macOS backend (stub)
└── package_managers/      # Package manager abstraction
    ├── __init__.py        # get_package_manager() factory + _REGISTRY dict
    ├── base.py            # PackageManager ABC
    └── pip.py             # pip implementation

tests/                     # pytest test suite
├── test_models.py         # Unit tests for data classes
├── test_package_managers.py
├── test_backends.py
├── test_fridge.py         # Tests for core Fridge logic
├── test_cli.py            # CLI integration tests
└── test_config.py

pyproject.toml             # Build config, dependencies, pytest settings
```

The `build/` directory is a stale build artifact — ignore it.

## Key architecture concepts

- **Backends** abstract over virtualenv management tools (e.g. `pyenv-venv-win` on Windows, `pyenv-virtualenv` on Linux/macOS). Each backend implements `VirtualenvBackend` ABC from `backends/base.py`.
- **Package managers** abstract over package installation tools (currently only `pip`). Each implements `PackageManager` ABC from `package_managers/base.py`.
- Both use a **registry pattern**: a `_REGISTRY` dict in their respective `__init__.py` files, with a `get_backend(name)` / `get_package_manager(name)` factory function.
- **`Fridge`** class in `fridge.py` orchestrates everything: it takes a `FridgeConfig`, resolves the backend and package manager, and exposes `backup_env()`, `backup_all()`, `restore_env()`, `diff_env()`, `list_backups()`.
- **`FridgeConfig`** in `config.py` handles OS-aware default paths and persistence to `config.json` inside the backup directory.

## How to set up for development

```bash
pip install -e ".[dev]"
```

This installs `pytest` and `pytest-cov` as dev dependencies. No other runtime dependencies — only the Python standard library (>=3.9).

## How to run tests

```bash
pytest                    # run all tests
pytest tests/test_models.py  # run a specific test file
pytest --cov=pyenv_fridge --cov-report=term-missing  # with coverage
```

Tests use `pytest` with `tmp_path` fixtures for filesystem isolation. Backends and subprocess calls are mocked — tests do not require `pyenv` to be installed.

## How to add a new feature

### Adding a new CLI command

1. Add a handler function `cmd_<name>(args) -> int` in `cli.py`.
2. Add a subparser in `build_parser()` in `cli.py`.
3. Set `parser.set_defaults(func=cmd_<name>)`.
4. Add tests in `tests/test_cli.py`.

### Adding a new virtualenv backend

1. Create `pyenv_fridge/backends/<name>.py`, subclass `VirtualenvBackend`.
2. Implement: `list_envs()`, `get_python_executable()`, `get_python_version()`, `create_env()`, and the `name` property.
3. Register in `pyenv_fridge/backends/__init__.py` by adding to `_REGISTRY`.
4. Add tests in `tests/test_backends.py`.

### Adding a new package manager

1. Create `pyenv_fridge/package_managers/<name>.py`, subclass `PackageManager`.
2. Implement: `freeze()`, `install_packages()`, and the `name` property.
3. Register in `pyenv_fridge/package_managers/__init__.py` by adding to `_REGISTRY`.
4. Add tests in `tests/test_package_managers.py`.

### Adding fields to the backup format

1. Add the field to `EnvBackup` or `PackageInfo` in `models.py`.
2. Update `to_dict()` and `from_dict()` to serialize/deserialize it.
3. Add tests in `tests/test_models.py`.

## Testing conventions

- Tests live in `tests/` and follow the naming pattern `test_<module>.py`.
- Use `pytest` fixtures (`tmp_path`, `monkeypatch`) for isolation.
- Mock external calls (subprocess, filesystem outside tmp_path) — do not rely on `pyenv` being installed.
- Test classes are named `Test<ClassName>`, test methods `test_<behavior>`.
- Each test file mirrors a source module (e.g. `test_models.py` tests `models.py`).

## Code style

- Python >=3.9, uses `from __future__ import annotations` for forward references.
- No third-party runtime dependencies — standard library only.
- Type hints on function signatures.
- Docstrings on public classes and methods.
- No linter/formatter configured — keep style consistent with existing code.
- **No emojis** — do not use emojis anywhere: code, comments, docstrings, print output, docs, or commit messages.
