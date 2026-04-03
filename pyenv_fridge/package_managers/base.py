"""Abstract base class for package managers."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List

from pyenv_fridge.models import PackageInfo


class PackageManager(ABC):
    """Abstraction over different package management systems.

    Concrete implementations provide the tool-specific logic to capture an
    environment's installed packages and to recreate them.

    To add a new package manager:

    1. Create a new module under ``pyenv_fridge/package_managers/``.
    2. Subclass :class:`PackageManager` and implement all abstract methods.
    3. Register the name in :func:`pyenv_fridge.package_managers.get_package_manager`.

    Extension notes
    ~~~~~~~~~~~~~~~
    * **conda**: Override :meth:`freeze` to call ``conda list --json`` and map
      the output to :class:`~pyenv_fridge.models.PackageInfo` objects, setting
      ``install_method="conda"`` where appropriate.
    * **uv**: Override :meth:`freeze` to call ``uv pip freeze`` and
      :meth:`install_packages` to call ``uv pip install``.
    """

    @abstractmethod
    def freeze(self, python_executable: str) -> List[PackageInfo]:
        """Capture installed packages in the environment using *python_executable*.

        Returns a list of :class:`~pyenv_fridge.models.PackageInfo` objects.
        """

    @abstractmethod
    def install_packages(
        self, python_executable: str, packages: List[PackageInfo]
    ) -> None:
        """Install *packages* into the environment identified by *python_executable*."""

    @property
    def name(self) -> str:
        """Human-readable package manager name, used in backup metadata."""
        return type(self).__name__
