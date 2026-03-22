"""Package manager factory for pyenv-fridge.

To add a new package manager:

1. Create a new module under ``pyenv_fridge/package_managers/`` that subclasses
   :class:`~pyenv_fridge.package_managers.base.PackageManager`.
2. Add an entry to ``_REGISTRY`` below mapping its name string to the class.
3. Document the new package manager in ``README.md``.
"""

from __future__ import annotations

from typing import Dict, Type

from pyenv_fridge.package_managers.base import PackageManager
from pyenv_fridge.package_managers.pip import PipPackageManager

_REGISTRY: Dict[str, Type[PackageManager]] = {
    "pip": PipPackageManager,
}


def get_package_manager(name: str) -> PackageManager:
    """Return an instantiated :class:`PackageManager` for *name*.

    Parameters
    ----------
    name:
        Package manager identifier string, e.g. ``"pip"``.

    Raises
    ------
    ValueError
        If *name* is not registered.
    """
    cls = _REGISTRY.get(name)
    if cls is None:
        available = ", ".join(sorted(_REGISTRY))
        raise ValueError(
            f"Unknown package manager {name!r}. "
            f"Available package managers: {available}"
        )
    return cls()


def list_package_managers() -> list:
    """Return a sorted list of registered package manager names."""
    return sorted(_REGISTRY.keys())
