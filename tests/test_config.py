"""Tests for pyenv_fridge.config."""

from __future__ import annotations

import json
import platform
from pathlib import Path

import pytest

from pyenv_fridge.config import FridgeConfig, _default_backup_dir


class TestDefaultPaths:
    def test_default_backup_dir_returns_path(self):
        result = _default_backup_dir()
        assert isinstance(result, Path)
        assert "pyenv-fridge" in str(result)

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
    def test_defaults(self):
        cfg = FridgeConfig()
        assert isinstance(cfg.backup_dir, Path)
        assert cfg.backend in ("pyenv-venv-win", "pyenv-virtualenv")
        assert cfg.package_manager == "pip"

    def test_config_path_derived_from_backup_dir(self, tmp_path):
        cfg = FridgeConfig(backup_dir=tmp_path / "backups")
        assert cfg.config_path == tmp_path / "backups" / "config.json"

    def test_envs_dir_derived_from_backup_dir(self, tmp_path):
        cfg = FridgeConfig(backup_dir=tmp_path / "backups")
        assert cfg.envs_dir == tmp_path / "backups" / "envs"

    def test_custom_values(self, tmp_path):
        cfg = FridgeConfig(
            backup_dir=tmp_path / "backups",
            backend="pyenv-venv-win",
            package_manager="pip",
        )
        assert cfg.backup_dir == tmp_path / "backups"
        assert cfg.backend == "pyenv-venv-win"

    def test_save_creates_file(self, tmp_path, monkeypatch):
        monkeypatch.setattr(
            "pyenv_fridge.config._default_backup_dir", lambda: tmp_path / "backups"
        )
        cfg = FridgeConfig(
            backup_dir=tmp_path / "backups",
            backend="pyenv-venv-win",
            package_manager="pip",
        )
        cfg.save()
        config_file = tmp_path / "backups" / "config.json"
        assert config_file.exists()
        data = json.loads(config_file.read_text())
        assert data["backend"] == "pyenv-venv-win"
        assert data["package_manager"] == "pip"
        assert "backup_dir" in data

    def test_save_creates_parent_dirs(self, tmp_path, monkeypatch):
        monkeypatch.setattr(
            "pyenv_fridge.config._default_backup_dir", lambda: tmp_path / "a" / "b" / "c"
        )
        cfg = FridgeConfig(backup_dir=tmp_path / "a" / "b" / "c")
        cfg.save()
        assert (tmp_path / "a" / "b" / "c" / "config.json").exists()

    def test_save_writes_redirect_when_not_default(self, tmp_path, monkeypatch):
        default_dir = tmp_path / "default"
        custom_dir = tmp_path / "custom"
        monkeypatch.setattr(
            "pyenv_fridge.config._default_backup_dir", lambda: default_dir
        )
        cfg = FridgeConfig(backup_dir=custom_dir)
        cfg.save()
        # Config written to both locations
        assert (custom_dir / "config.json").exists()
        assert (default_dir / "config.json").exists()
        redirect_data = json.loads((default_dir / "config.json").read_text())
        assert redirect_data["backup_dir"] == str(custom_dir)

    def test_load_nonexistent_returns_defaults(self, tmp_path):
        cfg = FridgeConfig.load(backup_dir=tmp_path / "nonexistent")
        assert isinstance(cfg, FridgeConfig)
        assert cfg.package_manager == "pip"

    def test_load_roundtrip(self, tmp_path, monkeypatch):
        monkeypatch.setattr(
            "pyenv_fridge.config._default_backup_dir", lambda: tmp_path / "mybackups"
        )
        cfg = FridgeConfig(
            backup_dir=tmp_path / "mybackups",
            backend="pyenv-virtualenv",
            package_manager="pip",
        )
        cfg.save()
        loaded = FridgeConfig.load(backup_dir=tmp_path / "mybackups")
        assert loaded.backup_dir == tmp_path / "mybackups"
        assert loaded.backend == "pyenv-virtualenv"
        assert loaded.package_manager == "pip"

    def test_load_follows_redirect(self, tmp_path, monkeypatch):
        default_dir = tmp_path / "default"
        custom_dir = tmp_path / "custom"
        monkeypatch.setattr(
            "pyenv_fridge.config._default_backup_dir", lambda: default_dir
        )
        # Save config with custom backup_dir
        cfg = FridgeConfig(
            backup_dir=custom_dir,
            backend="pyenv-virtualenv",
            package_manager="pip",
        )
        cfg.save()
        # Load from default — should follow redirect to custom
        loaded = FridgeConfig.load()
        assert loaded.backup_dir == custom_dir
        assert loaded.backend == "pyenv-virtualenv"

    def test_to_dict(self, tmp_path):
        cfg = FridgeConfig(backup_dir=tmp_path / "backups")
        d = cfg.to_dict()
        assert "backup_dir" in d
        assert "backend" in d
        assert "package_manager" in d
        assert "config_path" in d

    def test_repr(self):
        cfg = FridgeConfig()
        r = repr(cfg)
        assert "FridgeConfig" in r
        assert "pip" in r
