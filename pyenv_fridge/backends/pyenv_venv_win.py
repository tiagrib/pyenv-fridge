"""Windows backend using ``pyenv-win-venv``.

`pyenv-win-venv <https://github.com/pyenv-win/pyenv-win-venv>`_ provides the
``pyenv-venv`` CLI on Windows (``pyenv-win-venv`` is an alias).

Virtual environments are stored at::

    %USERPROFILE%\\.pyenv\\pyenv-win\\versions\\<env_name>\\

The Python interpreter lives at::

    <env_root>\\Scripts\\python.exe

Listing environments
~~~~~~~~~~~~~~~~~~~~
This backend invokes ``pyenv-venv list envs`` and parses one environment name
per line.

Extension notes
~~~~~~~~~~~~~~~
* To add support for a different Windows virtualenv tool, copy this file and
  override :meth:`list_envs` and :meth:`create_env`.
* The ``get_python_executable`` / ``get_python_version`` methods are generic
  enough to be reused if the env directory layout is the same.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path
from typing import List, Optional

from pyenv_fridge.backends.base import VirtualenvBackend


def _pyenv_root() -> Path:
    """Resolve the pyenv-win root directory.

    Tries (in order):

    1. ``PYENV_ROOT`` environment variable
    2. ``PYENV_HOME`` environment variable
    3. ``%USERPROFILE%\\.pyenv\\pyenv-win``
    """
    for var in ("PYENV_ROOT", "PYENV_HOME"):
        val = os.environ.get(var)
        if val:
            return Path(val)
    return Path.home() / ".pyenv" / "pyenv-win"


def _pyenv_venv_root() -> Path:
    """Resolve the pyenv-win-venv envs directory.

    Tries (in order):

    1. ``PYENV_VENV_HOME`` environment variable
    2. ``%USERPROFILE%\\.pyenv-win-venv\\envs``
    """
    val = os.environ.get("PYENV_VENV_HOME")
    if val:
        return Path(val)
    return Path.home() / ".pyenv-win-venv" / "envs"


# A plain version string such as "3.11.5" or "3.10.0-win32"
_VERSION_RE = re.compile(r"^\d+\.\d+\.\d+")


class PyenvVenvWinBackend(VirtualenvBackend):
    """Virtualenv backend for Windows using ``pyenv-win-venv``.

    Parameters
    ----------
    pyenv_root:
        Override the pyenv-win root directory.  Defaults to the value of
        :func:`_pyenv_root`.
    """

    def __init__(
        self,
        pyenv_root: Optional[Path] = None,
        venv_root: Optional[Path] = None,
    ) -> None:
        self._pyenv_root = pyenv_root or _pyenv_root()
        self._venv_root = venv_root or _pyenv_venv_root()

    @property
    def name(self) -> str:
        return "pyenv-venv-win"

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _versions_dir(self) -> Path:
        return self._pyenv_root / "versions"

    def _env_root(self, env_name: str) -> Path:
        """Return the root directory for a virtualenv.

        Checks the ``pyenv-win-venv`` envs directory first, then falls back to
        the pyenv-win ``versions`` directory.
        """
        venv_path = self._venv_root / env_name
        if venv_path.exists():
            return venv_path
        return self._versions_dir() / env_name

    def _is_valid_env_name(self, line: str) -> bool:
        """Return whether a ``pyenv-venv list envs`` output line is an env name."""
        lowered = line.lower()
        return (
            bool(line)
            and not lowered.startswith("pyenv")
            and not lowered.startswith("usage:")
            and not lowered.endswith(":")
            and not line.startswith("-")
            and not _VERSION_RE.match(line)
        )

    # ------------------------------------------------------------------
    # VirtualenvBackend interface
    # ------------------------------------------------------------------

    def list_envs(self) -> List[str]:
        """List virtualenvs by invoking ``pyenv-venv list envs``.

        Falls back to scanning the ``versions`` directory for directories that
        do not look like plain Python version strings (i.e. they are venvs).
        """
        try:
            result = subprocess.run(
                ["pyenv-venv", "list", "envs"],
                capture_output=True,
                text=True,
                check=True,
                shell=True,
            )
            envs = []
            for line in result.stdout.splitlines():
                line = line.strip()
                if self._is_valid_env_name(line):
                    envs.append(line)
            return envs
        except (FileNotFoundError, subprocess.CalledProcessError):
            return self._list_envs_from_filesystem()

    def _list_envs_from_filesystem(self) -> List[str]:
        """Fallback: scan the pyenv-win-venv envs directory and pyenv versions."""
        envs: List[str] = []
        # Primary: pyenv-win-venv envs directory
        if self._venv_root.exists():
            for entry in self._venv_root.iterdir():
                if entry.is_dir():
                    envs.append(entry.name)
        # Secondary: pyenv-win versions directory (non-version-string dirs)
        versions_dir = self._versions_dir()
        if versions_dir.exists():
            seen = set(envs)
            for entry in versions_dir.iterdir():
                if (
                    entry.is_dir()
                    and not _VERSION_RE.match(entry.name)
                    and entry.name not in seen
                ):
                    envs.append(entry.name)
        return sorted(envs)

    def get_python_executable(self, env_name: str) -> str:
        """Return path to ``python.exe`` inside the virtualenv."""
        env_root = self._env_root(env_name)
        # pyenv-venv-win places the interpreter under Scripts\
        candidates = [
            env_root / "Scripts" / "python.exe",
            env_root / "bin" / "python",  # unlikely on Windows but safe to check
        ]
        for candidate in candidates:
            if candidate.exists():
                return str(candidate)
        # Return the expected path even if it doesn't exist yet (e.g. before creation)
        return str(env_root / "Scripts" / "python.exe")

    def get_python_version(self, env_name: str) -> str:
        """Return the Python version for *env_name* by running ``python --version``."""
        python = self.get_python_executable(env_name)
        try:
            result = subprocess.run(
                [python, "--version"],
                capture_output=True,
                text=True,
                check=True,
            )
            # Output is "Python 3.11.5"
            output = result.stdout.strip() or result.stderr.strip()
            parts = output.split()
            return parts[1] if len(parts) >= 2 else output
        except (FileNotFoundError, subprocess.CalledProcessError):
            return "unknown"

    def create_env(self, env_name: str, python_version: str) -> None:
        """Create a new virtualenv via ``pyenv-venv install <version> <name>``."""
        subprocess.run(
            ["pyenv-venv", "install", python_version, env_name],
            check=True,
            shell=True,
        )
