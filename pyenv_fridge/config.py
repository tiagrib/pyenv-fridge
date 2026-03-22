"""Configuration management for pyenv-fridge.

The configuration file (``config.json``) lives inside the *backup directory*
alongside the ``envs/`` sub-directory that holds environment snapshots:

* **Windows**: ``%USERPROFILE%\\Documents\\pyenv-fridge\\config.json``
* **Linux / macOS**: ``~/.local/share/pyenv-fridge/config.json``

The backup directory can be overridden via ``fridge config set backup_dir …``.
When the backup directory is changed, a copy of the configuration is also kept
at the default location so that ``fridge`` can discover the redirect on the
next invocation.
"""

from __future__ import annotations

import json
import os
import platform
import sys
from pathlib import Path
from typing import Any, Dict, Optional


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

    The configuration file always lives at ``<backup_dir>/config.json``.
    Environment snapshots are stored under ``<backup_dir>/envs/``.

    Attributes:
        backup_dir: Root directory for pyenv-fridge data.
        backend: Virtualenv backend name (e.g. ``"pyenv-venv-win"``).
        package_manager: Package manager name (e.g. ``"pip"``).
    """

    CONFIG_FILENAME = "config.json"
    ENVS_DIRNAME = "envs"

    def __init__(
        self,
        backup_dir: Optional[Path] = None,
        backend: Optional[str] = None,
        package_manager: Optional[str] = None,
    ) -> None:
        self.backup_dir: Path = backup_dir or _default_backup_dir()
        self.backend: str = backend or _default_backend()
        self.package_manager: str = package_manager or _default_package_manager()

    @property
    def config_path(self) -> Path:
        """Path to the JSON config file (always ``backup_dir/config.json``)."""
        return self.backup_dir / self.CONFIG_FILENAME

    @property
    def envs_dir(self) -> Path:
        """Directory where environment snapshot JSON files are stored."""
        return self.backup_dir / self.ENVS_DIRNAME

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def _write_config(self, path: Path) -> None:
        """Serialise the current settings to *path*."""
        path.parent.mkdir(parents=True, exist_ok=True)
        data: Dict[str, Any] = {
            "backup_dir": str(self.backup_dir),
            "backend": self.backend,
            "package_manager": self.package_manager,
        }
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2)

    def save(self) -> None:
        """Write the current settings to ``backup_dir/config.json``.

        If *backup_dir* differs from the platform default, a copy of the
        configuration is also written to the default location so that
        ``fridge`` can discover the redirect on the next invocation.
        """
        self._write_config(self.config_path)
        default_bd = _default_backup_dir()
        if self.backup_dir.resolve() != default_bd.resolve():
            self._write_config(default_bd / self.CONFIG_FILENAME)

    @classmethod
    def load(cls, backup_dir: Optional[Path] = None) -> "FridgeConfig":
        """Load configuration from ``backup_dir/config.json``.

        When *backup_dir* is ``None`` the default location is tried first.
        If that file redirects to a different *backup_dir*, the configuration
        is re-loaded from there.

        If no file exists a default configuration is returned (nothing is
        written to disk until :meth:`save` is called).
        """
        bd = backup_dir or _default_backup_dir()
        path = bd / cls.CONFIG_FILENAME
        cfg = cls(backup_dir=bd)
        if path.exists():
            with open(path, "r", encoding="utf-8") as fh:
                data: Dict[str, Any] = json.load(fh)
            if "backend" in data:
                cfg.backend = data["backend"]
            if "package_manager" in data:
                cfg.package_manager = data["package_manager"]
            if "backup_dir" in data:
                stored_bd = Path(data["backup_dir"])
                if stored_bd.resolve() != bd.resolve():
                    # Redirect: the real config lives in a different backup_dir.
                    return cls.load(backup_dir=stored_bd)
                cfg.backup_dir = stored_bd
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
