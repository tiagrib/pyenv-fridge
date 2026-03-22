"""Core :class:`Fridge` class – backup, restore, and diff virtual environments.

The :class:`Fridge` orchestrates:

* A :class:`~pyenv_fridge.backends.base.VirtualenvBackend` – used to list
  environments, resolve their Python executables, and create new ones during
  restore.
* A :class:`~pyenv_fridge.package_managers.base.PackageManager` – used to
  capture installed packages (``freeze``) and reinstall them.
* A :class:`~pyenv_fridge.config.FridgeConfig` – supplies the backup directory
  and metadata written into each snapshot.
"""

from __future__ import annotations

import os
import platform
import sys
from pathlib import Path
from typing import Dict, List, Optional

from pyenv_fridge.backends.base import VirtualenvBackend
from pyenv_fridge.config import FridgeConfig
from pyenv_fridge.models import EnvBackup, EnvDiff, PackageDiff, PackageInfo
from pyenv_fridge.package_managers.base import PackageManager


class Fridge:
    """High-level API for backing up and restoring virtual environments.

    Parameters
    ----------
    config:
        :class:`~pyenv_fridge.config.FridgeConfig` instance.  If *None* a
        default configuration is loaded via
        :meth:`~pyenv_fridge.config.FridgeConfig.load`.
    backend:
        :class:`~pyenv_fridge.backends.base.VirtualenvBackend` instance.
        If *None* the backend named in *config* is instantiated automatically.
    package_manager:
        :class:`~pyenv_fridge.package_managers.base.PackageManager` instance.
        If *None* the package manager named in *config* is instantiated
        automatically.
    """

    def __init__(
        self,
        config: Optional[FridgeConfig] = None,
        backend: Optional[VirtualenvBackend] = None,
        package_manager: Optional[PackageManager] = None,
    ) -> None:
        if config is None:
            config = FridgeConfig.load()
        self.config = config

        if backend is None:
            from pyenv_fridge.backends import get_backend

            backend = get_backend(config.backend)
        self.backend = backend

        if package_manager is None:
            from pyenv_fridge.package_managers import get_package_manager

            package_manager = get_package_manager(config.package_manager)
        self.package_manager = package_manager

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _ensure_envs_dir(self) -> Path:
        self.config.envs_dir.mkdir(parents=True, exist_ok=True)
        return self.config.envs_dir

    def _backup_path(self, env_name: str) -> Path:
        return self._ensure_envs_dir() / f"{env_name}.json"

    def _platform_key(self) -> str:
        return platform.system().lower()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def backup_env(self, env_name: str) -> EnvBackup:
        """Backup a single virtual environment.

        Captures the Python version and the output of ``pip freeze`` (or the
        configured package manager) and writes a JSON snapshot to the backup
        directory.

        Parameters
        ----------
        env_name:
            Name of the virtual environment to back up.

        Returns
        -------
        EnvBackup
            The snapshot that was written.
        """
        python_exe = self.backend.get_python_executable(env_name)
        python_version = self.backend.get_python_version(env_name)
        packages = self.package_manager.freeze(python_exe)

        backup = EnvBackup(
            name=env_name,
            python_version=python_version,
            packages=packages,
            platform=self._platform_key(),
            backend=self.backend.name,
            package_manager=self.package_manager.name,
        )
        backup.save(str(self._backup_path(env_name)))
        return backup

    def backup_all(self) -> List[EnvBackup]:
        """Backup every virtual environment managed by the current backend.

        Returns
        -------
        list of EnvBackup
            One snapshot per environment that was successfully backed up.
        """
        env_names = self.backend.list_envs()
        backups: List[EnvBackup] = []
        for env_name in env_names:
            try:
                backup = self.backup_env(env_name)
                backups.append(backup)
                print(f"  ✓ Backed up '{env_name}' ({len(backup.packages)} packages)")
            except Exception as exc:
                print(f"  ✗ Failed to back up '{env_name}': {exc}")
        return backups

    def restore_env(
        self,
        env_name: str,
        *,
        create_if_missing: bool = True,
        reinstall: bool = False,
    ) -> None:
        """Restore a virtual environment from its backup snapshot.

        Parameters
        ----------
        env_name:
            Name of the environment to restore.  A backup file
            ``<backup_dir>/<env_name>.json`` must exist.
        create_if_missing:
            If *True* (default) the virtualenv is created via the backend
            before installing packages.  If *False* the env must already exist.
        reinstall:
            If *True* packages are installed even if the env already exists.
            Ignored when *create_if_missing* is *True* and the env is newly
            created.

        Raises
        ------
        FileNotFoundError
            If no backup file exists for *env_name*.
        """
        backup_path = self._backup_path(env_name)
        if not backup_path.exists():
            raise FileNotFoundError(
                f"No backup found for environment {env_name!r} "
                f"(expected {backup_path})"
            )

        backup = EnvBackup.from_file(str(backup_path))
        python_exe = self.backend.get_python_executable(env_name)

        env_exists = Path(python_exe).exists()
        if not env_exists:
            if create_if_missing:
                print(
                    f"  Creating environment '{env_name}' "
                    f"(Python {backup.python_version}) …"
                )
                self.backend.create_env(env_name, backup.python_version)
            else:
                raise RuntimeError(
                    f"Environment '{env_name}' does not exist and "
                    f"create_if_missing=False."
                )

        if not env_exists or reinstall:
            print(
                f"  Installing {len(backup.packages)} packages "
                f"into '{env_name}' …"
            )
            self.package_manager.install_packages(python_exe, backup.packages)
        print(f"  ✓ Environment '{env_name}' restored.")

    def diff_env(
        self,
        env_name: str,
        *,
        current_python_executable: Optional[str] = None,
    ) -> EnvDiff:
        """Compute the diff between the backup of *env_name* and a live environment.

        Parameters
        ----------
        env_name:
            Name whose backup snapshot is used as the reference.
        current_python_executable:
            Path to the Python interpreter of the *current* (live) environment.
            Defaults to the interpreter of the named environment.

        Returns
        -------
        EnvDiff
            Describes packages added, removed, or changed.

        Raises
        ------
        FileNotFoundError
            If no backup file exists for *env_name*.
        """
        backup_path = self._backup_path(env_name)
        if not backup_path.exists():
            raise FileNotFoundError(
                f"No backup found for environment {env_name!r} "
                f"(expected {backup_path})"
            )

        backup = EnvBackup.from_file(str(backup_path))

        if current_python_executable is None:
            current_python_executable = self.backend.get_python_executable(env_name)

        current_packages = self.package_manager.freeze(current_python_executable)

        return _compute_diff(env_name, backup, current_packages)

    def list_backups(self) -> List[EnvBackup]:
        """Return a list of all available backup snapshots.

        Returns
        -------
        list of EnvBackup
            Sorted alphabetically by environment name.
        """
        envs_dir = self.config.envs_dir
        if not envs_dir.exists():
            return []
        backups: List[EnvBackup] = []
        for json_file in sorted(envs_dir.glob("*.json")):
            try:
                backups.append(EnvBackup.from_file(str(json_file)))
            except Exception as exc:
                print(f"  [warn] Could not read {json_file.name}: {exc}")
        return backups


# ---------------------------------------------------------------------------
# Diff helper (module-level so it can be tested independently)
# ---------------------------------------------------------------------------


def _compute_diff(
    env_name: str,
    backup: EnvBackup,
    current_packages: List[PackageInfo],
) -> EnvDiff:
    """Compute the diff between *backup* packages and *current_packages*.

    Parameters
    ----------
    env_name:
        Name of the environment (used in the returned :class:`EnvDiff`).
    backup:
        The reference backup snapshot.
    current_packages:
        Packages currently installed in the live environment.
    """
    backup_by_name: Dict[str, PackageInfo] = backup.packages_by_name()
    current_by_name: Dict[str, PackageInfo] = {
        p.name.lower(): p for p in current_packages
    }

    diff = EnvDiff(env_name=env_name, backup_name=backup.name)

    backup_names = set(backup_by_name)
    current_names = set(current_by_name)

    for name in sorted(current_names - backup_names):
        diff.added.append(current_by_name[name])

    for name in sorted(backup_names - current_names):
        diff.removed.append(backup_by_name[name])

    for name in sorted(backup_names & current_names):
        bp = backup_by_name[name]
        cp = current_by_name[name]
        if bp.version != cp.version:
            diff.changed.append(PackageDiff(backup=bp, current=cp))

    return diff
