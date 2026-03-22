"""Tests for pyenv_fridge.config."""

from __future__ import annotations

import json
import platform
from pathlib import Path

import pytest

from pyenv_fridge.config import FridgeConfig, _default_backup_dir, _default_config_dir


class TestDefaultPaths:
    def test_default_config_dir_returns_path(self):
        result = _default_config_dir()
        assert isinstance(result, Path)
        assert "pyenv-fridge" in str(result)

    def test_default_backup_dir_returns_path(self):
        result = _default_backup_dir()
        assert isinstance(result, Path)
        assert "pyenv-fridge" in str(result)

    def test_windows_appdata_env_var(self, monkeypatch, tmp_path):
        monkeypatch.setenv("APPDATA", str(tmp_path))
        monkeypatch.setattr(platform, "system", lambda: "Windows")
        result = _default_config_dir()
        assert result == tmp_path / "pyenv-fridge"

    def test_linux_xdg_config_home(self, monkeypatch, tmp_path):
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
        monkeypatch.setattr(platform, "system", lambda: "Linux")
        result = _default_config_dir()
        assert result == tmp_path / "pyenv-fridge"

    def test_windows_backup_dir_userprofile(self, monkeypatch, tmp_path):
        monkeypatch.setenv("USERPROFILE", str(tmp_path))
        monkeypatch.setattr(platform, "system", lambda: "Windows")
        result = _default_backup_dir()
        assert result == tmp_path / "Documents" / "pyenv-fridge"

    def test_linux_backup_dir_xdg(self, monkeypatch, tmp_path):
        monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
        monkeypatch.setattr(platform, "system", lambda: "Linux")
        result = _default_backup_dir()
        assert result == tmp_path / "pyenv-fridge"


class TestFridgeConfig:
    def test_defaults(self, tmp_path):
        config_path = tmp_path / "config.json"
        cfg = FridgeConfig(config_path=config_path)
        assert isinstance(cfg.backup_dir, Path)
        assert cfg.backend in ("pyenv-venv-win", "pyenv-virtualenv")
        assert cfg.package_manager == "pip"

    def test_custom_values(self, tmp_path):
        cfg = FridgeConfig(
            backup_dir=tmp_path / "backups",
            backend="pyenv-venv-win",
            package_manager="pip",
            config_path=tmp_path / "config.json",
        )
        assert cfg.backup_dir == tmp_path / "backups"
        assert cfg.backend == "pyenv-venv-win"

    def test_save_creates_file(self, tmp_path):
        cfg = FridgeConfig(
            backup_dir=tmp_path / "backups",
            backend="pyenv-venv-win",
            package_manager="pip",
            config_path=tmp_path / "config.json",
        )
        cfg.save()
        assert (tmp_path / "config.json").exists()
        data = json.loads((tmp_path / "config.json").read_text())
        assert data["backend"] == "pyenv-venv-win"
        assert data["package_manager"] == "pip"
        assert "backup_dir" in data

    def test_save_creates_parent_dirs(self, tmp_path):
        nested = tmp_path / "a" / "b" / "c" / "config.json"
        cfg = FridgeConfig(
            backup_dir=tmp_path / "backups",
            config_path=nested,
        )
        cfg.save()
        assert nested.exists()

    def test_load_nonexistent_returns_defaults(self, tmp_path):
        cfg = FridgeConfig.load(config_path=tmp_path / "nonexistent.json")
        assert isinstance(cfg, FridgeConfig)
        assert cfg.package_manager == "pip"

    def test_load_roundtrip(self, tmp_path):
        cfg = FridgeConfig(
            backup_dir=tmp_path / "mybackups",
            backend="pyenv-virtualenv",
            package_manager="pip",
            config_path=tmp_path / "config.json",
        )
        cfg.save()
        loaded = FridgeConfig.load(config_path=tmp_path / "config.json")
        assert loaded.backup_dir == tmp_path / "mybackups"
        assert loaded.backend == "pyenv-virtualenv"
        assert loaded.package_manager == "pip"

    def test_to_dict(self, tmp_path):
        cfg = FridgeConfig(
            backup_dir=tmp_path / "backups",
            config_path=tmp_path / "config.json",
        )
        d = cfg.to_dict()
        assert "backup_dir" in d
        assert "backend" in d
        assert "package_manager" in d
        assert "config_path" in d

    def test_repr(self, tmp_path):
        cfg = FridgeConfig(config_path=tmp_path / "config.json")
        r = repr(cfg)
        assert "FridgeConfig" in r
        assert "pip" in r
