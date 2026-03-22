# pyenv-fridge

**Backup and restore system for Python virtual environments.**

`pyenv-fridge` captures snapshots of your `pyenv` virtual environments – each
snapshot records the environment name, Python version, and the full output of
`pip freeze` – and lets you restore them or inspect what has changed since the
last backup.

Snapshots are stored as plain JSON files in a configurable directory (e.g. a
cloud-synced folder) so you can carry your environments across machines.

---

## Table of contents

- [Features](#features)
- [Installation](#installation)
- [Quick start](#quick-start)
- [CLI reference](#cli-reference)
- [Configuration](#configuration)
- [Backup file format](#backup-file-format)
- [Architecture and extension plan](#architecture-and-extension-plan)
  - [Adding a new virtualenv backend](#adding-a-new-virtualenv-backend)
  - [Adding a new package manager](#adding-a-new-package-manager)
  - [Linux / macOS support](#linux--macos-support)
- [Development](#development)

---

## Features

- **Backup** – capture name, Python version, and installed packages for every
  (or a single) pyenv virtualenv.
- **Restore** – recreate a virtualenv from a snapshot; creates the env via the
  configured backend if it does not already exist.
- **Diff** – compare a stored snapshot against the packages currently installed
  in the live environment and show what was added, removed, or changed.
- **List** – show all available backup snapshots at a glance.
- **Configurable backup location** – point backups at a cloud drive, NAS, or
  any directory you like.
- **Modular backends** – swap the virtualenv management tool without changing
  anything else (e.g. from `pyenv-venv-win` to `pyenv-virtualenv`).
- **Modular package managers** – swap `pip` for `conda` or `uv` in the future
  without touching backup or restore logic.
- **pip vs conda tagging** – each package records its `install_method`
  (`"pip"` or `"conda"`) so restores can use the right tool per package.

---

## Installation

```bash
pip install pyenv-fridge          # from PyPI (once published)
# or, directly from source:
pip install git+https://github.com/tiagrib/pyenv-fridge.git
# or, from a local clone (run from repository root):
pip install .
```

The only runtime dependency is the Python standard library (≥ 3.9).

---

## Quick start

### Windows (pyenv-win-venv / `pyenv-venv`)

```powershell
# (Optional) Point backups at a cloud-synced folder
fridge config set backup_dir "C:\Users\you\OneDrive\pyenv-fridge"

# Show the active configuration
fridge config show

# Back up every virtual environment
fridge backup

# Back up a single environment
fridge backup my-data-science-env

# List all stored backups
fridge list

# Show what changed since the last backup of 'my-data-science-env'
fridge diff my-data-science-env

# Restore 'my-data-science-env' (creates it if it doesn't exist)
fridge restore my-data-science-env
```

### Linux / macOS (pyenv-virtualenv)

The commands are identical; `fridge` auto-detects the platform and uses the
appropriate backend (`pyenv-virtualenv` on Linux/macOS,
`pyenv-venv-win` on Windows, implemented via the `pyenv-venv` CLI from
`pyenv-win-venv`).

---

## CLI reference

```
fridge [--version] <command> [options]
```

### `fridge backup [ENV]`

Capture the state of a virtual environment.

| Argument / flag | Description |
|---|---|
| `ENV` (optional) | Name of the environment to back up. Omit to back up **all** environments. |

Backup files are written to `<backup_dir>/<ENV>.json`.

### `fridge restore ENV [--no-create] [--reinstall]`

Restore an environment from its backup snapshot.

| Argument / flag | Description |
|---|---|
| `ENV` | Name of the environment to restore. |
| `--no-create` | Fail instead of creating the env when it does not exist. |
| `--reinstall` | Re-install packages even when the env already exists. |

### `fridge diff ENV [--python PYTHON]`

Compare the stored backup of `ENV` against a live environment.

| Argument / flag | Description |
|---|---|
| `ENV` | Name whose backup is used as reference. |
| `--python PYTHON` | Path to a Python interpreter to use as the *current* env (defaults to the interpreter of `ENV`). |

Example output:

```
Diff for 'my-env'  (backup → current):
Added (1):
  + httpx==0.27.0
Removed (1):
  - requests==2.31.0
Changed (1):
  ~ numpy: 1.24.0 -> 1.26.4
```

### `fridge list`

Print all stored backup snapshots with Python version, package count, and
timestamp.

### `fridge setup`

Show setup guidance for the currently configured backend/package manager.
For Windows + `pyenv-venv-win`, this points to the `pyenv-win-venv` installer
and confirms the expected `pyenv-venv` command.

Use `--install-package-manager` to bootstrap the configured package manager
when supported (currently `pip` via `python -m ensurepip --upgrade`).

### `fridge config show`

Print the current configuration.

### `fridge config set KEY VALUE`

Update a configuration value and persist it.

| Key | Description |
|---|---|
| `backup_dir` | Directory where backup JSON files are stored. |
| `backend` | Virtualenv backend name (`pyenv-venv-win` or `pyenv-virtualenv`). |
| `package_manager` | Package manager name (`pip`). |

---

## Configuration

Configuration is loaded from (and saved to) a JSON file:

| OS | Config file | Default backup directory |
|---|---|---|
| **Windows** | `%APPDATA%\pyenv-fridge\config.json` | `%USERPROFILE%\Documents\pyenv-fridge` |
| **Linux / macOS** | `$XDG_CONFIG_HOME/pyenv-fridge/config.json` (or `~/.config/…`) | `$XDG_DATA_HOME/pyenv-fridge` (or `~/.local/share/…`) |

### Point backups at a cloud drive

```bash
fridge config set backup_dir "C:\Users\you\OneDrive\pyenv-fridge"
# or on Linux:
fridge config set backup_dir "$HOME/Dropbox/pyenv-fridge"
```

---

## Backup file format

Each snapshot is a single JSON file (`<env_name>.json`):

```json
{
  "name": "my-data-science-env",
  "python_version": "3.11.5",
  "created_at": "2024-06-01T12:00:00+00:00",
  "platform": "windows",
  "backend": "pyenv-venv-win",
  "package_manager": "pip",
  "packages": [
    { "name": "numpy",   "version": "1.26.4", "install_method": "pip" },
    { "name": "pandas",  "version": "2.2.1",  "install_method": "pip" },
    { "name": "pywin32", "version": "306",    "install_method": "pip",
      "platform_notes": { "linux": "Windows-only package" } }
  ]
}
```

The `install_method` field is ready to accommodate `"conda"` packages when the
conda package manager is added (see below).

The optional `platform_notes` dict can carry free-text hints per platform
(e.g. `"linux": "not available"`) so a restore on a different OS can skip or
substitute packages intelligently.

---

## Architecture and extension plan

```
pyenv_fridge/
├── __init__.py
├── cli.py                 # argparse CLI (fridge entry-point)
├── config.py              # FridgeConfig – OS-aware paths, persistence
├── fridge.py              # Fridge class – backup / restore / diff / list
├── models.py              # EnvBackup, PackageInfo, EnvDiff, PackageDiff
├── backends/
│   ├── __init__.py        # get_backend() factory + registry
│   ├── base.py            # VirtualenvBackend ABC
│   ├── pyenv_venv_win.py  # ✅ Windows – pyenv-venv-win (implemented via pyenv-venv CLI)
│   └── pyenv_virtualenv.py# 🔲 Linux/macOS – pyenv-virtualenv (stub)
└── package_managers/
    ├── __init__.py        # get_package_manager() factory + registry
    ├── base.py            # PackageManager ABC
    └── pip.py             # ✅ pip (implemented)
```

### Adding a new virtualenv backend

1. Create `pyenv_fridge/backends/my_backend.py` and subclass
   `VirtualenvBackend`:

   ```python
   from pyenv_fridge.backends.base import VirtualenvBackend

   class MyBackend(VirtualenvBackend):
       @property
       def name(self) -> str:
           return "my-backend"

       def list_envs(self): ...
       def get_python_executable(self, env_name): ...
       def get_python_version(self, env_name): ...
       def create_env(self, env_name, python_version): ...
   ```

2. Register it in `pyenv_fridge/backends/__init__.py`:

   ```python
   from pyenv_fridge.backends.my_backend import MyBackend
   _REGISTRY["my-backend"] = MyBackend
   ```

3. Switch to it:

   ```bash
   fridge config set backend my-backend
   ```

### Adding a new package manager

1. Create `pyenv_fridge/package_managers/conda.py` and subclass
   `PackageManager`:

   ```python
   from pyenv_fridge.package_managers.base import PackageManager

   class CondaPackageManager(PackageManager):
       @property
       def name(self) -> str:
           return "conda"

       def freeze(self, python_executable): ...
       def install_packages(self, python_executable, packages): ...
   ```

   Set `install_method="conda"` on packages that come from conda channels so
   the restore step uses `conda install` for them and `pip install` for the
   rest.

2. Register it in `pyenv_fridge/package_managers/__init__.py`:

   ```python
   from pyenv_fridge.package_managers.conda import CondaPackageManager
   _REGISTRY["conda"] = CondaPackageManager
   ```

3. Switch to it:

   ```bash
   fridge config set package_manager conda
   ```

### Linux / macOS support

The `PyenvVirtualenvBackend` stub in
`pyenv_fridge/backends/pyenv_virtualenv.py` uses the same `pyenv virtualenv`
command interface as the Windows backend and differs only in the interpreter
path (`bin/python` vs `Scripts/python.exe`).

**TODO for Linux/macOS completion:**

- [ ] Implement and test `list_envs` with a live `pyenv-virtualenv` installation.
- [ ] Verify `get_python_executable` path on all common distros.
- [ ] Add CI matrix entries for Linux runners.
- [ ] Document distro-specific pyenv setup steps in this README.

---

## Development

```bash
# Clone and install dev dependencies
git clone https://github.com/tiagrib/pyenv-fridge.git
cd pyenv-fridge
pip install -e ".[dev]"

# Run the test suite
pytest

# Run with coverage
pytest --cov=pyenv_fridge --cov-report=term-missing
```
