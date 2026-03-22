"""Configuration management for pyenv-fridge.

The configuration is stored as a JSON file in an OS-appropriate location:

* **Windows**: ``%APPDATA%\\pyenv-fridge\\config.json``
* **Linux / macOS**: ``$XDG_CONFIG_HOME/pyenv-fridge/config.json``
  (falls back to ``~/.config/pyenv-fridge/config.json``)

The default *backup directory* (where ``.json`` snapshot files are written) is:

* **Windows**: ``%USERPROFILE%\\Documents\\pyenv-fridge``
* **Linux / macOS**: ``~/.local/share/pyenv-fridge``

Both paths can be overridden via the configuration file or programmatically.
"""

from __future__ import annotations

import json
import os
import platform
import sys
from pathlib import Path
from typing import Any, Dict, Optional


def _default_config_dir() -> Path:
    """Return the OS-appropriate directory for the config file."""
    system = platform.system()
    if system == "Windows":
        appdata = os.environ.get("APPDATA")
        if appdata:
            return Path(appdata) / "pyenv-fridge"
        return Path.home() / "AppData" / "Roaming" / "pyenv-fridge"
    # Linux / macOS – follow XDG Base Directory Specification
    xdg = os.environ.get("XDG_CONFIG_HOME")
    if xdg:
        return Path(xdg) / "pyenv-fridge"
    return Path.home() / ".config" / "pyenv-fridge"


def _default_backup_dir() -> Path:
    """Return the OS-appropriate default backup directory."""
    system = platform.system()
    if system == "Windows":
        userprofile = os.environ.get("USERPROFILE")
        if userprofile:
            return Path(userprofile) / "Documents" / "pyenv-fridge"
        return Path.home() / "Documents" / "pyenv-fridge"
    # Linux / macOS – XDG data home
    xdg = os.environ.get("XDG_DATA_HOME")
    if xdg:
        return Path(xdg) / "pyenv-fridge"
    return Path.home() / ".local" / "share" / "pyenv-fridge"


def _default_backend() -> str:
    """Return the name of the default virtualenv backend for this OS."""
    if platform.system() == "Windows":
        return "pyenv-venv-win"
    return "pyenv-virtualenv"


def _default_package_manager() -> str:
    return "pip"


class FridgeConfig:
    """Persistent configuration for pyenv-fridge.

    Settings are loaded from (and saved to) a JSON file.  Any key may also be
    overridden programmatically; call :meth:`save` to persist the changes.

    Attributes:
        backup_dir: Directory where backup ``.json`` files are stored.
        backend: Virtualenv backend name (e.g. ``"pyenv-venv-win"``).
        package_manager: Package manager name (e.g. ``"pip"``).
        config_path: Path to the JSON config file itself.
    """

    CONFIG_FILENAME = "config.json"

    def __init__(
        self,
        backup_dir: Optional[Path] = None,
        backend: Optional[str] = None,
        package_manager: Optional[str] = None,
        config_path: Optional[Path] = None,
    ) -> None:
        self.config_path: Path = config_path or (
            _default_config_dir() / self.CONFIG_FILENAME
        )
        self.backup_dir: Path = backup_dir or _default_backup_dir()
        self.backend: str = backend or _default_backend()
        self.package_manager: str = package_manager or _default_package_manager()

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def save(self) -> None:
        """Write the current settings to :attr:`config_path`."""
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        data: Dict[str, Any] = {
            "backup_dir": str(self.backup_dir),
            "backend": self.backend,
            "package_manager": self.package_manager,
        }
        with open(self.config_path, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2)

    @classmethod
    def load(cls, config_path: Optional[Path] = None) -> "FridgeConfig":
        """Load configuration from *config_path* (or the default location).

        If the file does not exist a default configuration is returned (nothing
        is written to disk until :meth:`save` is called).
        """
        path = config_path or (_default_config_dir() / cls.CONFIG_FILENAME)
        cfg = cls(config_path=path)
        if path.exists():
            with open(path, "r", encoding="utf-8") as fh:
                data: Dict[str, Any] = json.load(fh)
            if "backup_dir" in data:
                cfg.backup_dir = Path(data["backup_dir"])
            if "backend" in data:
                cfg.backend = data["backend"]
            if "package_manager" in data:
                cfg.package_manager = data["package_manager"]
        return cfg

    def to_dict(self) -> Dict[str, Any]:
        return {
            "backup_dir": str(self.backup_dir),
            "backend": self.backend,
            "package_manager": self.package_manager,
            "config_path": str(self.config_path),
        }

    def __repr__(self) -> str:
        return (
            f"FridgeConfig(backup_dir={str(self.backup_dir)!r}, "
            f"backend={self.backend!r}, "
            f"package_manager={self.package_manager!r})"
        )
