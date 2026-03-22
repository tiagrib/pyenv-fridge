"""Linux / macOS backend using ``pyenv-virtualenv``.

``pyenv-virtualenv`` (https://github.com/pyenv/pyenv-virtualenv) is a plugin
for `pyenv <https://github.com/pyenv/pyenv>`_ that adds the
``pyenv virtualenv`` sub-command on Linux and macOS.

Virtual environments are stored at::

    $PYENV_ROOT/versions/<env_name>/

with a symlink from::

    $PYENV_ROOT/versions/<python_version>/envs/<env_name> -> ../../../<env_name>

The Python interpreter lives at::

    <env_root>/bin/python

Implementation status
~~~~~~~~~~~~~~~~~~~~~
This backend is a **stub**.  The Windows backend
(:mod:`pyenv_fridge.backends.pyenv_venv_win`) is the primary implementation.
The Linux backend follows the same command interface (``pyenv virtualenv``,
``pyenv virtualenvs --bare``) so the implementation is almost identical; it
differs only in the interpreter path (``bin/python`` vs ``Scripts/python.exe``).

TODO: Implement and test :meth:`list_envs`, :meth:`get_python_executable`,
:meth:`get_python_version`, and :meth:`create_env` for Linux/macOS.
"""

from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path
from typing import List, Optional

from pyenv_fridge.backends.base import VirtualenvBackend


def _pyenv_root() -> Path:
    val = os.environ.get("PYENV_ROOT")
    if val:
        return Path(val)
    return Path.home() / ".pyenv"


_VERSION_RE = re.compile(r"^\d+\.\d+\.\d+")


class PyenvVirtualenvBackend(VirtualenvBackend):
    """Virtualenv backend for Linux/macOS using ``pyenv-virtualenv``.

    .. note::
        This backend is a **stub** and is not yet fully implemented.
        Contributions welcome – see :mod:`pyenv_fridge.backends.pyenv_venv_win`
        for the reference implementation.

    Parameters
    ----------
    pyenv_root:
        Override the pyenv root directory.  Defaults to the value of
        ``PYENV_ROOT`` or ``~/.pyenv``.
    """

    def __init__(self, pyenv_root: Optional[Path] = None) -> None:
        self._pyenv_root = pyenv_root or _pyenv_root()

    @property
    def name(self) -> str:
        return "pyenv-virtualenv"

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
        """List virtualenvs by invoking ``pyenv virtualenvs --bare``."""
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
        versions_dir = self._versions_dir()
        if not versions_dir.exists():
            return []
        envs = []
        for entry in versions_dir.iterdir():
            if entry.is_dir() and not _VERSION_RE.match(entry.name):
                envs.append(entry.name)
        return sorted(envs)

    def get_python_executable(self, env_name: str) -> str:
        """Return path to the Python interpreter inside the virtualenv."""
        env_root = self._env_root(env_name)
        candidate = env_root / "bin" / "python"
        return str(candidate)

    def get_python_version(self, env_name: str) -> str:
        """Return the Python version string for *env_name*."""
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
        """Create a new virtualenv via ``pyenv virtualenv <version> <name>``."""
        subprocess.run(
            ["pyenv", "virtualenv", python_version, env_name],
            check=True,
        )
