"""Tests for pyenv_fridge.backends."""

from __future__ import annotations

from pathlib import Path

import pytest

from pyenv_fridge.backends import get_backend, list_backends
from pyenv_fridge.backends.pyenv_venv_win import (
    PyenvVenvWinBackend,
    _VERSION_RE,
    _pyenv_root,
)
from pyenv_fridge.backends.pyenv_virtualenv import PyenvVirtualenvBackend


# ---------------------------------------------------------------------------
# Backend registry
# ---------------------------------------------------------------------------


class TestBackendRegistry:
    def test_list_backends(self):
        backends = list_backends()
        assert "pyenv-venv-win" in backends
        assert "pyenv-virtualenv" in backends

    def test_get_backend_pyenv_venv_win(self):
        backend = get_backend("pyenv-venv-win")
        assert isinstance(backend, PyenvVenvWinBackend)

    def test_get_backend_pyenv_virtualenv(self):
        backend = get_backend("pyenv-virtualenv")
        assert isinstance(backend, PyenvVirtualenvBackend)

    def test_get_backend_unknown_raises(self):
        with pytest.raises(ValueError, match="Unknown virtualenv backend"):
            get_backend("no-such-backend")


# ---------------------------------------------------------------------------
# PyenvVenvWinBackend
# ---------------------------------------------------------------------------


class TestPyenvVenvWinBackend:
    def _make_backend(self, tmp_path: Path) -> PyenvVenvWinBackend:
        return PyenvVenvWinBackend(pyenv_root=tmp_path, venv_root=tmp_path / "venvs")

    def test_name(self, tmp_path):
        backend = self._make_backend(tmp_path)
        assert backend.name == "pyenv-venv-win"

    def test_get_python_executable_scripts_path(self, tmp_path):
        backend = self._make_backend(tmp_path)
        exe = backend.get_python_executable("myenv")
        # On Windows-layout, Scripts\python.exe is expected
        assert "myenv" in exe
        assert "python" in exe.lower()

    def test_get_python_executable_returns_existing_file(self, tmp_path):
        # Create the expected Scripts\python.exe path
        env_dir = tmp_path / "versions" / "myenv" / "Scripts"
        env_dir.mkdir(parents=True)
        python_exe = env_dir / "python.exe"
        python_exe.touch()
        backend = self._make_backend(tmp_path)
        result = backend.get_python_executable("myenv")
        assert result == str(python_exe)

    def test_list_envs_from_filesystem_empty(self, tmp_path):
        backend = self._make_backend(tmp_path)
        # versions dir doesn't exist yet
        assert backend._list_envs_from_filesystem() == []

    def test_list_envs_from_filesystem_filters_version_dirs(self, tmp_path):
        versions = tmp_path / "versions"
        versions.mkdir(parents=True)
        (versions / "3.11.5").mkdir()  # plain Python version – should be excluded
        (versions / "myenv").mkdir()  # virtualenv – should be included
        (versions / "anotherenv").mkdir()
        backend = self._make_backend(tmp_path)
        envs = backend._list_envs_from_filesystem()
        assert "myenv" in envs
        assert "anotherenv" in envs
        assert "3.11.5" not in envs

    def test_list_envs_from_filesystem_sorted(self, tmp_path):
        versions = tmp_path / "versions"
        versions.mkdir(parents=True)
        (versions / "zenv").mkdir()
        (versions / "aenv").mkdir()
        (versions / "menv").mkdir()
        backend = self._make_backend(tmp_path)
        envs = backend._list_envs_from_filesystem()
        assert envs == sorted(envs)

    def test_list_envs_falls_back_to_filesystem(self, tmp_path, mocker):
        # pyenv command not found → falls back to filesystem scan
        mocker.patch(
            "pyenv_fridge.backends.pyenv_venv_win.subprocess.run",
            side_effect=FileNotFoundError,
        )
        versions = tmp_path / "versions"
        versions.mkdir(parents=True)
        (versions / "myenv").mkdir()
        backend = self._make_backend(tmp_path)
        envs = backend.list_envs()
        assert "myenv" in envs

    def test_list_envs_parses_pyenv_venv_output(self, tmp_path, mocker):
        mock_result = mocker.MagicMock()
        mock_result.stdout = "myenv\nanotherenv\n"
        mocker.patch(
            "pyenv_fridge.backends.pyenv_venv_win.subprocess.run",
            return_value=mock_result,
        )
        backend = self._make_backend(tmp_path)
        envs = backend.list_envs()
        assert "myenv" in envs
        assert "anotherenv" in envs
    
    def test_list_envs_ignores_cli_noise(self, tmp_path, mocker):
        mock_result = mocker.MagicMock()
        mock_result.stdout = "pyenv-win-venv v0.6\nusage: pyenv-venv ...\n-myflag\nmyenv\n"
        mocker.patch(
            "pyenv_fridge.backends.pyenv_venv_win.subprocess.run",
            return_value=mock_result,
        )
        backend = self._make_backend(tmp_path)
        envs = backend.list_envs()
        assert envs == ["myenv"]
        assert "pyenv-win-venv v0.6" not in envs

    def test_get_python_version_parses_output(self, tmp_path, mocker):
        mock_result = mocker.MagicMock()
        mock_result.stdout = "Python 3.11.5"
        mock_result.stderr = ""
        mocker.patch(
            "pyenv_fridge.backends.pyenv_venv_win.subprocess.run",
            return_value=mock_result,
        )
        backend = self._make_backend(tmp_path)
        version = backend.get_python_version("myenv")
        assert version == "3.11.5"

    def test_get_python_version_fallback_on_error(self, tmp_path, mocker):
        mocker.patch(
            "pyenv_fridge.backends.pyenv_venv_win.subprocess.run",
            side_effect=FileNotFoundError,
        )
        backend = self._make_backend(tmp_path)
        version = backend.get_python_version("myenv")
        assert version == "unknown"

    def test_create_env_calls_pyenv_venv(self, tmp_path, mocker):
        mock_run = mocker.patch(
            "pyenv_fridge.backends.pyenv_venv_win.subprocess.run"
        )
        backend = self._make_backend(tmp_path)
        backend.create_env("newenv", "3.11.5")
        mock_run.assert_called_once()
        call_args = mock_run.call_args[0][0]
        assert "pyenv-venv" in call_args
        assert "install" in call_args
        assert "3.11.5" in call_args
        assert "newenv" in call_args


# ---------------------------------------------------------------------------
# Version regex
# ---------------------------------------------------------------------------


class TestVersionRegex:
    def test_matches_standard_versions(self):
        assert _VERSION_RE.match("3.11.5")
        assert _VERSION_RE.match("3.10.0")
        assert _VERSION_RE.match("2.7.18")

    def test_does_not_match_env_names(self):
        assert not _VERSION_RE.match("myenv")
        assert not _VERSION_RE.match("data-science")
        assert not _VERSION_RE.match("ml_project")


# ---------------------------------------------------------------------------
# PyenvVirtualenvBackend (stub, basic coverage)
# ---------------------------------------------------------------------------


class TestPyenvVirtualenvBackend:
    def test_name(self, tmp_path):
        backend = PyenvVirtualenvBackend(pyenv_root=tmp_path)
        assert backend.name == "pyenv-virtualenv"

    def test_get_python_executable_bin_python(self, tmp_path):
        backend = PyenvVirtualenvBackend(pyenv_root=tmp_path)
        exe = backend.get_python_executable("myenv")
        assert "myenv" in exe
        assert "python" in exe

    def test_list_envs_from_filesystem(self, tmp_path):
        versions = tmp_path / "versions"
        versions.mkdir()
        (versions / "myenv").mkdir()
        (versions / "3.11.5").mkdir()
        backend = PyenvVirtualenvBackend(pyenv_root=tmp_path)
        envs = backend._list_envs_from_filesystem()
        assert "myenv" in envs
        assert "3.11.5" not in envs
