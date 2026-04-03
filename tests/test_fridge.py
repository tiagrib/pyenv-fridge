"""Tests for pyenv_fridge.fridge (Fridge class and _compute_diff)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from pyenv_fridge.config import FridgeConfig
from pyenv_fridge.fridge import Fridge, _compute_diff
from pyenv_fridge.models import EnvBackup, EnvDiff, PackageInfo


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_config(tmp_path: Path) -> FridgeConfig:
    return FridgeConfig(
        backup_dir=tmp_path / "backups",
        backend="pyenv-venv-win",
        package_manager="pip",
    )


def _make_mock_backend(
    envs=None,
    python_exe="/path/to/python",
    python_version="3.11.5",
) -> MagicMock:
    backend = MagicMock()
    backend.name = "pyenv-venv-win"
    backend.list_envs.return_value = envs or []
    backend.get_python_executable.return_value = python_exe
    backend.get_python_version.return_value = python_version
    return backend


def _make_mock_pm(packages=None) -> MagicMock:
    pm = MagicMock()
    pm.name = "pip"
    pm.freeze.return_value = packages or []
    return pm


# ---------------------------------------------------------------------------
# _compute_diff
# ---------------------------------------------------------------------------


class TestComputeDiff:
    def _backup(self, packages):
        return EnvBackup(
            name="myenv",
            python_version="3.11.5",
            packages=packages,
        )

    def test_no_changes(self):
        pkgs = [
            PackageInfo(name="numpy", version="1.24.0"),
            PackageInfo(name="pandas", version="2.0.0"),
        ]
        backup = self._backup(pkgs)
        diff = _compute_diff("myenv", backup, pkgs)
        assert not diff.has_changes

    def test_added_packages(self):
        backup_pkgs = [PackageInfo(name="numpy", version="1.24.0")]
        current_pkgs = [
            PackageInfo(name="numpy", version="1.24.0"),
            PackageInfo(name="newpkg", version="1.0.0"),
        ]
        diff = _compute_diff("myenv", self._backup(backup_pkgs), current_pkgs)
        assert len(diff.added) == 1
        assert diff.added[0].name == "newpkg"
        assert len(diff.removed) == 0
        assert len(diff.changed) == 0

    def test_removed_packages(self):
        backup_pkgs = [
            PackageInfo(name="numpy", version="1.24.0"),
            PackageInfo(name="oldpkg", version="0.9.0"),
        ]
        current_pkgs = [PackageInfo(name="numpy", version="1.24.0")]
        diff = _compute_diff("myenv", self._backup(backup_pkgs), current_pkgs)
        assert len(diff.removed) == 1
        assert diff.removed[0].name == "oldpkg"

    def test_changed_version(self):
        backup_pkgs = [PackageInfo(name="numpy", version="1.24.0")]
        current_pkgs = [PackageInfo(name="numpy", version="1.25.0")]
        diff = _compute_diff("myenv", self._backup(backup_pkgs), current_pkgs)
        assert len(diff.changed) == 1
        assert diff.changed[0].backup.version == "1.24.0"
        assert diff.changed[0].current.version == "1.25.0"

    def test_combined_changes(self):
        backup_pkgs = [
            PackageInfo(name="numpy", version="1.24.0"),
            PackageInfo(name="removed-pkg", version="0.1.0"),
        ]
        current_pkgs = [
            PackageInfo(name="numpy", version="1.25.0"),
            PackageInfo(name="added-pkg", version="2.0.0"),
        ]
        diff = _compute_diff("myenv", self._backup(backup_pkgs), current_pkgs)
        assert len(diff.added) == 1
        assert len(diff.removed) == 1
        assert len(diff.changed) == 1

    def test_case_insensitive_matching(self):
        backup_pkgs = [PackageInfo(name="NumPy", version="1.24.0")]
        current_pkgs = [PackageInfo(name="numpy", version="1.24.0")]
        diff = _compute_diff("myenv", self._backup(backup_pkgs), current_pkgs)
        assert not diff.has_changes


# ---------------------------------------------------------------------------
# Fridge
# ---------------------------------------------------------------------------


class TestFridgeBackupEnv:
    def test_backup_env_creates_json_file(self, tmp_path):
        config = _make_config(tmp_path)
        backend = _make_mock_backend(
            python_exe="/path/python",
            python_version="3.11.5",
        )
        pm = _make_mock_pm(
            packages=[
                PackageInfo(name="numpy", version="1.24.0"),
                PackageInfo(name="pandas", version="2.0.0"),
            ]
        )
        fridge = Fridge(config=config, backend=backend, package_manager=pm)
        backup = fridge.backup_env("myenv")

        assert backup.name == "myenv"
        assert backup.python_version == "3.11.5"
        assert len(backup.packages) == 2

        backup_file = config.envs_dir / "myenv.json"
        assert backup_file.exists()

        loaded = EnvBackup.from_file(str(backup_file))
        assert loaded.name == "myenv"
        assert loaded.python_version == "3.11.5"

    def test_backup_env_metadata(self, tmp_path):
        config = _make_config(tmp_path)
        backend = _make_mock_backend()
        backend.name = "pyenv-venv-win"
        pm = _make_mock_pm()
        pm.name = "pip"
        fridge = Fridge(config=config, backend=backend, package_manager=pm)
        backup = fridge.backup_env("myenv")

        assert backup.backend == "pyenv-venv-win"
        assert backup.package_manager == "pip"
        assert backup.platform != ""  # OS key is set

    def test_backup_env_calls_correct_python(self, tmp_path):
        config = _make_config(tmp_path)
        backend = _make_mock_backend(python_exe="/custom/python")
        pm = _make_mock_pm()
        fridge = Fridge(config=config, backend=backend, package_manager=pm)
        fridge.backup_env("myenv")

        pm.freeze.assert_called_once_with("/custom/python")


class TestFridgeBackupAll:
    def test_backup_all_returns_list(self, tmp_path):
        config = _make_config(tmp_path)
        backend = _make_mock_backend(envs=["env1", "env2"])
        pm = _make_mock_pm(packages=[PackageInfo(name="numpy", version="1.24.0")])
        fridge = Fridge(config=config, backend=backend, package_manager=pm)
        backups = fridge.backup_all()
        assert len(backups) == 2
        names = {b.name for b in backups}
        assert "env1" in names
        assert "env2" in names

    def test_backup_all_tolerates_errors(self, tmp_path, capsys):
        config = _make_config(tmp_path)
        backend = _make_mock_backend(envs=["good-env", "bad-env"])
        pm = MagicMock()
        pm.name = "pip"

        def side_effect(python_exe):
            if "bad-env" in backend.get_python_executable.call_args[0][0]:
                raise RuntimeError("simulated failure")
            return []

        backend.get_python_executable.side_effect = lambda n: (
            "/path/bad" if n == "bad-env" else "/path/good"
        )
        pm.freeze.side_effect = lambda exe: (
            [] if "good" in exe else (_ for _ in ()).throw(RuntimeError("fail"))
        )

        fridge = Fridge(config=config, backend=backend, package_manager=pm)
        backups = fridge.backup_all()
        # Only good-env succeeded
        assert len(backups) == 1
        assert backups[0].name == "good-env"
        captured = capsys.readouterr()
        assert "bad-env" in captured.out


class TestFridgeListBackups:
    def test_list_backups_empty(self, tmp_path):
        config = _make_config(tmp_path)
        backend = _make_mock_backend()
        pm = _make_mock_pm()
        fridge = Fridge(config=config, backend=backend, package_manager=pm)
        assert fridge.list_backups() == []

    def test_list_backups_returns_all(self, tmp_path):
        config = _make_config(tmp_path)
        config.envs_dir.mkdir(parents=True)
        for name in ("alpha", "beta", "gamma"):
            b = EnvBackup(name=name, python_version="3.11.5", packages=[])
            b.save(str(config.envs_dir / f"{name}.json"))

        backend = _make_mock_backend()
        pm = _make_mock_pm()
        fridge = Fridge(config=config, backend=backend, package_manager=pm)
        backups = fridge.list_backups()
        assert len(backups) == 3
        names = {b.name for b in backups}
        assert names == {"alpha", "beta", "gamma"}


class TestFridgeDiffEnv:
    def test_diff_env_no_backup_raises(self, tmp_path):
        config = _make_config(tmp_path)
        backend = _make_mock_backend()
        pm = _make_mock_pm()
        fridge = Fridge(config=config, backend=backend, package_manager=pm)
        with pytest.raises(FileNotFoundError, match="No backup found"):
            fridge.diff_env("nonexistent")

    def test_diff_env_detects_changes(self, tmp_path):
        config = _make_config(tmp_path)
        config.envs_dir.mkdir(parents=True)

        backup = EnvBackup(
            name="myenv",
            python_version="3.11.5",
            packages=[
                PackageInfo(name="numpy", version="1.24.0"),
                PackageInfo(name="removed-pkg", version="0.1.0"),
            ],
        )
        backup.save(str(config.envs_dir / "myenv.json"))

        backend = _make_mock_backend(python_exe="/path/python")
        pm = _make_mock_pm(
            packages=[
                PackageInfo(name="numpy", version="1.25.0"),  # changed
                PackageInfo(name="added-pkg", version="2.0.0"),  # new
                # removed-pkg is gone
            ]
        )
        fridge = Fridge(config=config, backend=backend, package_manager=pm)
        diff = fridge.diff_env("myenv")

        assert diff.has_changes
        assert len(diff.added) == 1
        assert diff.added[0].name == "added-pkg"
        assert len(diff.removed) == 1
        assert diff.removed[0].name == "removed-pkg"
        assert len(diff.changed) == 1

    def test_diff_env_custom_python_executable(self, tmp_path):
        config = _make_config(tmp_path)
        config.envs_dir.mkdir(parents=True)
        backup = EnvBackup(name="myenv", python_version="3.11.5", packages=[])
        backup.save(str(config.envs_dir / "myenv.json"))

        backend = _make_mock_backend()
        pm = _make_mock_pm()
        fridge = Fridge(config=config, backend=backend, package_manager=pm)
        fridge.diff_env("myenv", current_python_executable="/custom/python")

        pm.freeze.assert_called_once_with("/custom/python")


class TestFridgeRestoreEnv:
    def test_restore_env_no_backup_raises(self, tmp_path):
        config = _make_config(tmp_path)
        backend = _make_mock_backend()
        pm = _make_mock_pm()
        fridge = Fridge(config=config, backend=backend, package_manager=pm)
        with pytest.raises(FileNotFoundError):
            fridge.restore_env("nonexistent")

    def test_restore_creates_env_when_missing(self, tmp_path):
        config = _make_config(tmp_path)
        config.envs_dir.mkdir(parents=True)

        backup = EnvBackup(
            name="myenv",
            python_version="3.11.5",
            packages=[PackageInfo(name="numpy", version="1.24.0")],
        )
        backup.save(str(config.envs_dir / "myenv.json"))

        backend = _make_mock_backend(python_exe="/nonexistent/python")
        pm = _make_mock_pm()
        fridge = Fridge(config=config, backend=backend, package_manager=pm)

        # Python executable doesn't exist → create_env should be called
        fridge.restore_env("myenv", create_if_missing=True)
        backend.create_env.assert_called_once_with("myenv", "3.11.5")
        pm.install_packages.assert_called_once()

    def test_restore_no_create_missing_env_raises(self, tmp_path):
        config = _make_config(tmp_path)
        config.envs_dir.mkdir(parents=True)

        backup = EnvBackup(name="myenv", python_version="3.11.5", packages=[])
        backup.save(str(config.envs_dir / "myenv.json"))

        backend = _make_mock_backend(python_exe="/nonexistent/python")
        pm = _make_mock_pm()
        fridge = Fridge(config=config, backend=backend, package_manager=pm)
        with pytest.raises(RuntimeError, match="does not exist"):
            fridge.restore_env("myenv", create_if_missing=False)

    def test_restore_reinstall_existing_env(self, tmp_path):
        config = _make_config(tmp_path)
        config.envs_dir.mkdir(parents=True)

        # Write a real Python executable path so Path(python_exe).exists() is True
        python_dir = tmp_path / "python_envs" / "myenv"
        python_dir.mkdir(parents=True)
        python_exe = python_dir / "python"
        python_exe.touch()

        backup = EnvBackup(
            name="myenv",
            python_version="3.11.5",
            packages=[PackageInfo(name="numpy", version="1.24.0")],
        )
        backup.save(str(config.envs_dir / "myenv.json"))

        backend = _make_mock_backend(python_exe=str(python_exe))
        pm = _make_mock_pm()
        fridge = Fridge(config=config, backend=backend, package_manager=pm)
        fridge.restore_env("myenv", reinstall=True)

        backend.create_env.assert_not_called()
        pm.install_packages.assert_called_once()
