"""Windows backend using ``pyenv-venv-win``.

``pyenv-venv-win`` (https://github.com/pyenv-win/pyenv-venv) is a plugin for
`pyenv-win <https://github.com/pyenv-win/pyenv-win>`_ that adds the
``pyenv virtualenv`` sub-command on Windows.

Virtual environments are stored at::

    %USERPROFILE%\\.pyenv\\pyenv-win\\versions\\<env_name>\\

The Python interpreter lives at::

    <env_root>\\Scripts\\python.exe

Listing environments
~~~~~~~~~~~~~~~~~~~~
This backend invokes ``pyenv virtualenvs --bare`` and filters out lines that
look like plain Python version strings (e.g. ``3.11.5``) so that only
virtualenv names are returned.

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


# A plain version string such as "3.11.5" or "3.10.0-win32"
_VERSION_RE = re.compile(r"^\d+\.\d+\.\d+")


class PyenvVenvWinBackend(VirtualenvBackend):
    """Virtualenv backend for Windows using ``pyenv-venv-win``.

    Parameters
    ----------
    pyenv_root:
        Override the pyenv-win root directory.  Defaults to the value of
        :func:`_pyenv_root`.
    """

    def __init__(self, pyenv_root: Optional[Path] = None) -> None:
        self._pyenv_root = pyenv_root or _pyenv_root()

    @property
    def name(self) -> str:
        return "pyenv-venv-win"

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _versions_dir(self) -> Path:
        return self._pyenv_root / "versions"

    def _env_root(self, env_name: str) -> Path:
        return self._versions_dir() / env_name

    # ------------------------------------------------------------------
    # VirtualenvBackend interface
    # ------------------------------------------------------------------

    def list_envs(self) -> List[str]:
        """List virtualenvs by invoking ``pyenv virtualenvs --bare``.

        Falls back to scanning the ``versions`` directory for directories that
        do not look like plain Python version strings (i.e. they are venvs).
        """
        try:
            result = subprocess.run(
                ["pyenv", "virtualenvs", "--bare"],
                capture_output=True,
                text=True,
                check=True,
            )
            envs = []
            for line in result.stdout.splitlines():
                line = line.strip()
                if line and not _VERSION_RE.match(line):
                    envs.append(line)
            return envs
        except (FileNotFoundError, subprocess.CalledProcessError):
            return self._list_envs_from_filesystem()

    def _list_envs_from_filesystem(self) -> List[str]:
        """Fallback: scan the versions directory."""
        versions_dir = self._versions_dir()
        if not versions_dir.exists():
            return []
        envs = []
        for entry in versions_dir.iterdir():
            if entry.is_dir() and not _VERSION_RE.match(entry.name):
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
        """Create a new virtualenv via ``pyenv virtualenv <version> <name>``."""
        subprocess.run(
            ["pyenv", "virtualenv", python_version, env_name],
            check=True,
        )
