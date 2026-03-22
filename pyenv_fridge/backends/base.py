"""Abstract base class for virtualenv backends."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List


class VirtualenvBackend(ABC):
    """Abstraction over different virtualenv management systems.

    Concrete implementations provide the OS/tool-specific logic to list
    environments, resolve their Python executables, and create new ones.

    To add a new backend:

    1. Create a new module under ``pyenv_fridge/backends/``.
    2. Subclass :class:`VirtualenvBackend` and implement all abstract methods.
    3. Register the backend name in :func:`pyenv_fridge.backends.get_backend`.

    Extension points
    ~~~~~~~~~~~~~~~~
    * **conda**: Override :meth:`list_envs` to call ``conda env list`` and
      :meth:`get_python_executable` to locate each env's interpreter.
    * **venv / virtualenv** (plain): Override to scan a configurable envs root
      directory (e.g. ``~/.virtualenvs``).
    """

    # ------------------------------------------------------------------
    # Required interface
    # ------------------------------------------------------------------

    @abstractmethod
    def list_envs(self) -> List[str]:
        """Return a list of virtual environment names managed by this backend."""

    @abstractmethod
    def get_python_executable(self, env_name: str) -> str:
        """Return the absolute path to the Python interpreter for *env_name*."""

    @abstractmethod
    def get_python_version(self, env_name: str) -> str:
        """Return the Python version string (e.g. ``"3.11.5"``) for *env_name*."""

    @abstractmethod
    def create_env(self, env_name: str, python_version: str) -> None:
        """Create a new virtual environment named *env_name* using *python_version*."""

    # ------------------------------------------------------------------
    # Optional helpers (may be overridden)
    # ------------------------------------------------------------------

    @property
    def name(self) -> str:
        """Human-readable backend name, used in backup metadata."""
        return type(self).__name__
