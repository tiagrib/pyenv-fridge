"""pip package manager implementation.

Captures installed packages via ``pip freeze`` and installs them via
``pip install -r``.

Package-method detection
~~~~~~~~~~~~~~~~~~~~~~~~
All packages surfaced by ``pip freeze`` are assumed to have been installed via
pip (``install_method="pip"``).  In a future extension, conda metadata could be
inspected to re-classify packages that were actually installed through conda
into ``install_method="conda"``.

The ``platform_notes`` field of :class:`~pyenv_fridge.models.PackageInfo` is
left empty by this implementation.  A future enhancement could populate it
automatically for well-known packages that require different treatment on
different platforms (e.g. ``pywin32``, ``pyobjc``).
"""

from __future__ import annotations

import subprocess
from typing import List

from pyenv_fridge.models import PackageInfo
from pyenv_fridge.package_managers.base import PackageManager


def parse_pip_freeze(output: str) -> List[PackageInfo]:
    """Parse the output of ``pip freeze`` into a list of :class:`PackageInfo`.

    Lines starting with ``#`` or ``-e`` (editable installs) are currently
    skipped.  Editable installs are logged as warnings; full support could be
    added in a future version.

    Parameters
    ----------
    output:
        Raw string output from ``pip freeze``.
    """
    packages: List[PackageInfo] = []
    for line in output.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("-e"):
            # Editable installs cannot be restored via a plain pip install;
            # skip them for now.
            continue
        if "==" in line:
            name, _, version = line.partition("==")
            packages.append(
                PackageInfo(name=name.strip(), version=version.strip(), install_method="pip")
            )
        elif (
            line.startswith("-r")
            or line.startswith("--index-url")
            or line.startswith("--extra-index-url")
            or line.startswith("--trusted-host")
            or line.startswith("--hash")
            or line.startswith("--find-links")
        ):
            # pip option directives – skip
            continue
        else:
            # Unexpected format – store with empty version so it isn't silently dropped
            packages.append(PackageInfo(name=line, version="", install_method="pip"))
    return packages


class PipPackageManager(PackageManager):
    """Package manager implementation that uses ``pip``."""

    @property
    def name(self) -> str:
        return "pip"

    def freeze(self, python_executable: str) -> List[PackageInfo]:
        """Run ``pip freeze`` in the environment and return parsed packages.

        Parameters
        ----------
        python_executable:
            Absolute path to the Python interpreter whose pip will be used.
        """
        result = subprocess.run(
            [python_executable, "-m", "pip", "freeze"],
            capture_output=True,
            text=True,
            check=True,
        )
        return parse_pip_freeze(result.stdout)

    def install_packages(
        self, python_executable: str, packages: List[PackageInfo]
    ) -> None:
        """Install *packages* using pip.

        Only packages with ``install_method == "pip"`` are installed; others
        are skipped with a warning printed to stdout.

        Parameters
        ----------
        python_executable:
            Absolute path to the Python interpreter whose pip will be used.
        packages:
            List of packages to install.
        """
        pip_packages = []
        for pkg in packages:
            if pkg.install_method != "pip":
                print(
                    f"  [skip] {pkg.name}=={pkg.version} "
                    f"(install_method={pkg.install_method!r}, not handled by pip)"
                )
                continue
            spec = f"{pkg.name}=={pkg.version}" if pkg.version else pkg.name
            pip_packages.append(spec)

        if not pip_packages:
            return

        subprocess.run(
            [python_executable, "-m", "pip", "install", *pip_packages],
            check=True,
        )
