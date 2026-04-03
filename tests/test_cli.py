"""Tests for pyenv_fridge.cli."""

from __future__ import annotations

from pathlib import Path
import sys
from unittest.mock import MagicMock, patch

import pytest

from pyenv_fridge.cli import build_parser, main
from pyenv_fridge.config import FridgeConfig
from pyenv_fridge.models import EnvBackup, PackageInfo


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_config(tmp_path: Path) -> FridgeConfig:
    return FridgeConfig(
        backup_dir=tmp_path / "backups",
        backend="pyenv-venv-win",
        package_manager="pip",
    )


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------


class TestBuildParser:
    def test_backup_no_env(self):
        parser = build_parser()
        args = parser.parse_args(["backup"])
        assert args.command == "backup"
        assert args.env_name is None

    def test_backup_with_env(self):
        parser = build_parser()
        args = parser.parse_args(["backup", "myenv"])
        assert args.env_name == "myenv"

    def test_restore_required_env(self):
        parser = build_parser()
        args = parser.parse_args(["restore", "myenv"])
        assert args.env_name == "myenv"
        assert args.no_create is False
        assert args.reinstall is False

    def test_restore_flags(self):
        parser = build_parser()
        args = parser.parse_args(["restore", "myenv", "--no-create", "--reinstall"])
        assert args.no_create is True
        assert args.reinstall is True

    def test_diff_required_env(self):
        parser = build_parser()
        args = parser.parse_args(["diff", "myenv"])
        assert args.env_name == "myenv"
        assert args.python is None

    def test_diff_custom_python(self):
        parser = build_parser()
        args = parser.parse_args(["diff", "myenv", "--python", "/custom/python"])
        assert args.python == "/custom/python"

    def test_list(self):
        parser = build_parser()
        args = parser.parse_args(["list"])
        assert args.command == "list"

    def test_setup(self):
        parser = build_parser()
        args = parser.parse_args(["setup"])
        assert args.command == "setup"
        assert args.install_package_manager is False

    def test_setup_with_install_package_manager_flag(self):
        parser = build_parser()
        args = parser.parse_args(["setup", "--install-package-manager"])
        assert args.command == "setup"
        assert args.install_package_manager is True

    def test_config_show(self):
        parser = build_parser()
        args = parser.parse_args(["config", "show"])
        assert args.command == "config"
        assert args.config_cmd == "show"

    def test_config_set(self):
        parser = build_parser()
        args = parser.parse_args(["config", "set", "backup_dir", "/some/path"])
        assert args.config_cmd == "set"
        assert args.key == "backup_dir"
        assert args.value == "/some/path"

    def test_version_flag(self, capsys):
        parser = build_parser()
        with pytest.raises(SystemExit) as exc_info:
            parser.parse_args(["--version"])
        assert exc_info.value.code == 0


# ---------------------------------------------------------------------------
# cmd_list
# ---------------------------------------------------------------------------


class TestCmdList:
    def test_list_no_backups(self, tmp_path, capsys):
        config = _make_config(tmp_path)
        with patch("pyenv_fridge.cli.FridgeConfig.load", return_value=config):
            with patch("pyenv_fridge.cli.Fridge") as MockFridge:
                instance = MockFridge.return_value
                instance.list_backups.return_value = []
                code = main(["list"])
        assert code == 0
        captured = capsys.readouterr()
        assert "No backups" in captured.out

    def test_list_with_backups(self, tmp_path, capsys):
        config = _make_config(tmp_path)
        backups = [
            EnvBackup(
                name="myenv",
                python_version="3.11.5",
                packages=[PackageInfo(name="numpy", version="1.24.0")],
                created_at="2024-01-15T10:30:00",
            )
        ]
        with patch("pyenv_fridge.cli.FridgeConfig.load", return_value=config):
            with patch("pyenv_fridge.cli.Fridge") as MockFridge:
                instance = MockFridge.return_value
                instance.list_backups.return_value = backups
                code = main(["list"])
        assert code == 0
        captured = capsys.readouterr()
        assert "myenv" in captured.out
        assert "3.11.5" in captured.out


# ---------------------------------------------------------------------------
# cmd_backup
# ---------------------------------------------------------------------------


class TestCmdBackup:
    def test_backup_all(self, tmp_path, capsys):
        config = _make_config(tmp_path)
        backups = [
            EnvBackup(name="env1", python_version="3.11.5", packages=[]),
            EnvBackup(name="env2", python_version="3.10.0", packages=[]),
        ]
        with patch("pyenv_fridge.cli.FridgeConfig.load", return_value=config):
            with patch("pyenv_fridge.cli.Fridge") as MockFridge:
                instance = MockFridge.return_value
                instance.backup_all.return_value = backups
                instance._backup_path = MagicMock()
                code = main(["backup"])
        assert code == 0
        captured = capsys.readouterr()
        assert "2 environment" in captured.out

    def test_backup_single_env(self, tmp_path, capsys):
        config = _make_config(tmp_path)
        backup = EnvBackup(
            name="myenv",
            python_version="3.11.5",
            packages=[PackageInfo(name="numpy", version="1.24.0")],
        )
        with patch("pyenv_fridge.cli.FridgeConfig.load", return_value=config):
            with patch("pyenv_fridge.cli.Fridge") as MockFridge:
                instance = MockFridge.return_value
                instance.backup_env.return_value = backup
                instance._backup_path.return_value = tmp_path / "myenv.json"
                code = main(["backup", "myenv"])
        assert code == 0

    def test_backup_single_env_error(self, tmp_path, capsys):
        config = _make_config(tmp_path)
        with patch("pyenv_fridge.cli.FridgeConfig.load", return_value=config):
            with patch("pyenv_fridge.cli.Fridge") as MockFridge:
                instance = MockFridge.return_value
                instance.backup_env.side_effect = RuntimeError("test error")
                code = main(["backup", "myenv"])
        assert code == 1


# ---------------------------------------------------------------------------
# cmd_diff
# ---------------------------------------------------------------------------


class TestCmdDiff:
    def test_diff_no_backup(self, tmp_path, capsys):
        config = _make_config(tmp_path)
        with patch("pyenv_fridge.cli.FridgeConfig.load", return_value=config):
            with patch("pyenv_fridge.cli.Fridge") as MockFridge:
                instance = MockFridge.return_value
                instance.diff_env.side_effect = FileNotFoundError("No backup")
                code = main(["diff", "myenv"])
        assert code == 1

    def test_diff_no_changes(self, tmp_path, capsys):
        from pyenv_fridge.models import EnvDiff

        config = _make_config(tmp_path)
        diff = EnvDiff(env_name="myenv", backup_name="myenv")
        with patch("pyenv_fridge.cli.FridgeConfig.load", return_value=config):
            with patch("pyenv_fridge.cli.Fridge") as MockFridge:
                instance = MockFridge.return_value
                instance.diff_env.return_value = diff
                code = main(["diff", "myenv"])
        assert code == 0
        captured = capsys.readouterr()
        assert "No differences" in captured.out


# ---------------------------------------------------------------------------
# cmd_config
# ---------------------------------------------------------------------------


class TestCmdConfig:
    def test_config_show(self, tmp_path, capsys):
        config = _make_config(tmp_path)
        with patch("pyenv_fridge.cli.FridgeConfig.load", return_value=config):
            code = main(["config", "show"])
        assert code == 0
        captured = capsys.readouterr()
        assert "backup_dir" in captured.out
        assert "backend" in captured.out

    def test_config_set_backup_dir(self, tmp_path, capsys):
        config = _make_config(tmp_path)
        with patch("pyenv_fridge.cli.FridgeConfig.load", return_value=config), \
             patch("pyenv_fridge.config._default_backup_dir", return_value=tmp_path / "backups"):
            code = main(["config", "set", "backup_dir", str(tmp_path / "newbackups")])
        assert code == 0
        assert config.backup_dir == tmp_path / "newbackups"

    def test_config_set_invalid_key(self, tmp_path, capsys):
        config = _make_config(tmp_path)
        with patch("pyenv_fridge.cli.FridgeConfig.load", return_value=config):
            code = main(["config", "set", "invalid_key", "value"])
        assert code == 1
        captured = capsys.readouterr()
        assert "Unknown config key" in captured.err


class TestCmdSetup:
    def test_setup_default_windows_backend_hint(self, tmp_path, capsys):
        config = _make_config(tmp_path)
        with patch("pyenv_fridge.cli.FridgeConfig.load", return_value=config):
            code = main(["setup"])
        assert code == 0
        captured = capsys.readouterr()
        assert "configured backend: pyenv-venv-win" in captured.out
        assert "pyenv-win-venv" in captured.out

    def test_setup_linux_backend_hint(self, tmp_path, capsys):
        config = _make_config(tmp_path)
        config.backend = "pyenv-virtualenv"
        with patch("pyenv_fridge.cli.FridgeConfig.load", return_value=config):
            code = main(["setup"])
        assert code == 0
        captured = capsys.readouterr()
        assert "pyenv-virtualenv" in captured.out

    def test_setup_install_package_manager_for_pip(self, tmp_path, capsys):
        config = _make_config(tmp_path)
        with patch("pyenv_fridge.cli.FridgeConfig.load", return_value=config):
            with patch("pyenv_fridge.cli.subprocess.run") as mock_run:
                code = main(["setup", "--install-package-manager"])
        assert code == 0
        mock_run.assert_called_once()
        args = mock_run.call_args[0][0]
        assert args[:3] == [sys.executable, "-m", "ensurepip"]
        captured = capsys.readouterr()
        assert "pip bootstrap complete" in captured.out

    def test_setup_install_package_manager_custom_pm_fails(self, tmp_path, capsys):
        config = _make_config(tmp_path)
        config.package_manager = "conda"
        with patch("pyenv_fridge.cli.FridgeConfig.load", return_value=config):
            code = main(["setup", "--install-package-manager"])
        assert code == 1
        captured = capsys.readouterr()
        assert "currently supported only for 'pip'" in captured.err
