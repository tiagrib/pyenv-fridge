"""uv package manager implementation.

Captures installed packages via ``uv pip list --format=json`` and installs
them via ``uv pip install``.

``uv`` is a drop-in replacement for pip, so packages with
``install_method`` of either ``"pip"`` or ``"uv"`` are handled.
"""

from __future__ import annotations

import json
import subprocess
from typing import List

from pyenv_fridge.models import PackageInfo
from pyenv_fridge.package_managers.base import PackageManager

# Packages that are part of the environment scaffolding, not user packages.
_EXCLUDED = frozenset(("pip", "setuptools", "wheel"))


def parse_uv_pip_list(output: str) -> List[PackageInfo]:
    """Parse the JSON output of ``uv pip list --format=json``.

    Parameters
    ----------
    output:
        Raw JSON string from ``uv pip list --format=json``.
    """
    entries = json.loads(output) if output.strip() else []
    packages: List[PackageInfo] = []
    for entry in entries:
        name = entry.get("name", "")
        if name.lower() in _EXCLUDED:
            continue
        packages.append(
            PackageInfo(
                name=name,
                version=entry.get("version", ""),
                install_method="uv",
            )
        )
    return packages


class UvPackageManager(PackageManager):
    """Package manager implementation using ``uv``."""

    @property
    def name(self) -> str:
        return "uv"

    def freeze(self, python_executable: str) -> List[PackageInfo]:
        """Run ``uv pip list --format=json`` and return parsed packages."""
        result = subprocess.run(
            ["uv", "pip", "list", "--format=json", "--python", python_executable],
            capture_output=True,
            text=True,
            check=True,
        )
        return parse_uv_pip_list(result.stdout)

    def install_packages(
        self,
        python_executable: str,
        packages: List[PackageInfo],
        *,
        no_deps: bool = False,
    ) -> None:
        """Install *packages* using ``uv pip install``.

        Packages with ``install_method`` of ``"pip"`` or ``"uv"`` are both
        accepted since uv is pip-compatible.

        Parameters
        ----------
        no_deps:
            If *True*, pass ``--no-deps`` to skip dependency resolution.
        """
        compatible = ("pip", "uv")
        specs: List[str] = []
        for pkg in packages:
            if pkg.install_method not in compatible:
                print(
                    f"  [skip] {pkg.name}=={pkg.version} "
                    f"(install_method={pkg.install_method!r}, not handled by uv)"
                )
                continue
            spec = f"{pkg.name}=={pkg.version}" if pkg.version else pkg.name
            specs.append(spec)

        if not specs:
            return

        cmd = ["uv", "pip", "install", "--python", python_executable]
        if no_deps:
            cmd.append("--no-deps")
        cmd.extend(specs)
        subprocess.run(cmd, check=True)
