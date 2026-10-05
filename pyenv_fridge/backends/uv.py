"""Backend using ``uv`` for Python version and virtualenv management.

`uv <https://docs.astral.sh/uv/>`_ is a fast Python package and project
manager that can also install Python versions and create virtual environments.

Unlike pyenv-based backends, ``uv`` does not maintain a central directory of
named environments.  This backend stores environments under a configurable
root directory (default: ``~/.pyenv-fridge/uv-envs``).

Virtual environments are stored at::

    <envs_root>/<env_name>/

The Python interpreter lives at::

    <envs_root>/<env_name>/Scripts/python.exe   (Windows)
    <envs_root>/<env_name>/bin/python            (Unix)
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import List, Optional

from pyenv_fridge.backends.base import VirtualenvBackend


def _default_envs_root() -> Path:
    """Return the default directory for uv-managed environments."""
    val = os.environ.get("FRIDGE_UV_ENVS")
    if val:
        return Path(val)
    return Path.home() / ".pyenv-fridge" / "uv-envs"


class UvBackend(VirtualenvBackend):
    """Virtualenv backend using ``uv``.

    Parameters
    ----------
    envs_root:
        Override the directory where environments are stored.
        Defaults to ``~/.pyenv-fridge/uv-envs`` (or ``$FRIDGE_UV_ENVS``).
    """

    def __init__(self, envs_root: Optional[Path] = None) -> None:
        self._envs_root = envs_root or _default_envs_root()

    @property
    def name(self) -> str:
        return "uv"

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _env_root(self, env_name: str) -> Path:
        return self._envs_root / env_name

    # ------------------------------------------------------------------
    # VirtualenvBackend interface
    # ------------------------------------------------------------------

    def list_envs(self) -> List[str]:
        """List environments by scanning the envs root directory."""
        if not self._envs_root.exists():
            return []
        return sorted(
            entry.name
            for entry in self._envs_root.iterdir()
            if entry.is_dir()
        )

    def get_python_executable(self, env_name: str) -> str:
        env_root = self._env_root(env_name)
        if sys.platform == "win32":
            candidate = env_root / "Scripts" / "python.exe"
        else:
            candidate = env_root / "bin" / "python"
        return str(candidate)

    def get_python_version(self, env_name: str) -> str:
        python = self.get_python_executable(env_name)
        try:
            result = subprocess.run(
                [python, "--version"],
                capture_output=True,
                text=True,
                check=True,
            )
            output = result.stdout.strip() or result.stderr.strip()
            parts = output.split()
            return parts[1] if len(parts) >= 2 else output
        except (FileNotFoundError, subprocess.CalledProcessError):
            return "unknown"

    def create_env(self, env_name: str, python_version: str) -> None:
        """Create a virtualenv via ``uv venv``.

        Ensures the requested Python version is installed first via
        ``uv python install``.
        """
        # Ensure the Python version is available
        subprocess.run(
            ["uv", "python", "install", python_version],
            check=True,
        )
        # Create the venv
        dest = self._env_root(env_name)
        dest.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(
            ["uv", "venv", str(dest), "--python", python_version],
            check=True,
        )
