"""Backend factory for pyenv-fridge.

To add a new virtualenv backend:

1. Create a new module under ``pyenv_fridge/backends/`` that subclasses
   :class:`~pyenv_fridge.backends.base.VirtualenvBackend`.
2. Add an entry to ``_REGISTRY`` below mapping its name string to the class.
3. Document the new backend in ``README.md``.
"""

from __future__ import annotations

from typing import Dict, Type

from pyenv_fridge.backends.base import VirtualenvBackend
from pyenv_fridge.backends.pyenv_venv_win import PyenvVenvWinBackend
from pyenv_fridge.backends.pyenv_virtualenv import PyenvVirtualenvBackend

_REGISTRY: Dict[str, Type[VirtualenvBackend]] = {
    "pyenv-venv-win": PyenvVenvWinBackend,
    "pyenv-virtualenv": PyenvVirtualenvBackend,
}


def get_backend(name: str) -> VirtualenvBackend:
    """Return an instantiated :class:`VirtualenvBackend` for *name*.

    Parameters
    ----------
    name:
        Backend identifier string, e.g. ``"pyenv-venv-win"`` or
        ``"pyenv-virtualenv"``.

    Raises
    ------
    ValueError
        If *name* is not registered.
    """
    cls = _REGISTRY.get(name)
    if cls is None:
        available = ", ".join(sorted(_REGISTRY))
        raise ValueError(
            f"Unknown virtualenv backend {name!r}. "
            f"Available backends: {available}"
        )
    return cls()


def list_backends() -> list:
    """Return a sorted list of registered backend names."""
    return sorted(_REGISTRY.keys())
