"""Configuration management for pyenv-fridge.

The configuration file (``config.json``) lives inside the *backup directory*
alongside the ``envs/`` sub-directory that holds environment snapshots:

* **Windows**: ``%USERPROFILE%\\Documents\\pyenv-fridge\\config.json``
* **Linux / macOS**: ``~/.local/share/pyenv-fridge/config.json``

The backup directory can be overridden via ``fridge config set location …``.
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


def _default_location() -> Path:
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

    The configuration file always lives at ``<location>/config.json``.
    Environment snapshots are stored under ``<location>/envs/``.

    Attributes:
        location: Root directory for pyenv-fridge data.
        backend: Virtualenv backend name (e.g. ``"pyenv-venv-win"``).
        package_manager: Package manager name (e.g. ``"pip"``).
    """

    CONFIG_FILENAME = "config.json"
    ENVS_DIRNAME = "envs"

    def __init__(
        self,
        location: Optional[Path] = None,
        backend: Optional[str] = None,
        package_manager: Optional[str] = None,
    ) -> None:
        self.location: Path = location or _default_location()
        self.backend: str = backend or _default_backend()
        self.package_manager: str = package_manager or _default_package_manager()

    @property
    def config_path(self) -> Path:
        """Path to the JSON config file (always ``location/config.json``)."""
        return self.location / self.CONFIG_FILENAME

    @property
    def envs_dir(self) -> Path:
        """Directory where environment snapshot JSON files are stored."""
        return self.location / self.ENVS_DIRNAME

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def _write_config(self, path: Path) -> None:
        """Serialise the current settings to *path*."""
        path.parent.mkdir(parents=True, exist_ok=True)
        data: Dict[str, Any] = {
            "location": str(self.location),
            "backend": self.backend,
            "package_manager": self.package_manager,
        }
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2)

    def save(self) -> None:
        """Write the current settings to ``location/config.json``.

        If *location* differs from the platform default, a copy of the
        configuration is also written to the default location so that
        ``fridge`` can discover the redirect on the next invocation.
        """
        self._write_config(self.config_path)
        default_bd = _default_location()
        if self.location.resolve() != default_bd.resolve():
            self._write_config(default_bd / self.CONFIG_FILENAME)

    @classmethod
    def load(cls, location: Optional[Path] = None) -> "FridgeConfig":
        """Load configuration from ``location/config.json``.

        When *location* is ``None`` the default location is tried first.
        If that file redirects to a different *location*, the configuration
        is re-loaded from there.

        If no file exists a default configuration is returned (nothing is
        written to disk until :meth:`save` is called).
        """
        bd = location or _default_location()
        path = bd / cls.CONFIG_FILENAME
        cfg = cls(location=bd)
        if path.exists():
            with open(path, "r", encoding="utf-8") as fh:
                data: Dict[str, Any] = json.load(fh)
            if "backend" in data:
                cfg.backend = data["backend"]
            if "package_manager" in data:
                cfg.package_manager = data["package_manager"]
            if "location" in data:
                stored_bd = Path(data["location"])
                if stored_bd.resolve() != bd.resolve():
                    # Redirect: the real config lives in a different location.
                    return cls.load(location=stored_bd)
                cfg.location = stored_bd
        return cfg

    def to_dict(self) -> Dict[str, Any]:
        return {
            "location": str(self.location),
            "backend": self.backend,
            "package_manager": self.package_manager,
            "config_path": str(self.config_path),
        }

    def __repr__(self) -> str:
        return (
            f"FridgeConfig(location={str(self.location)!r}, "
            f"backend={self.backend!r}, "
            f"package_manager={self.package_manager!r})"
        )
