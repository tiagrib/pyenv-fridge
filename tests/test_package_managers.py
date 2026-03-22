"""Tests for pyenv_fridge.package_managers.pip."""

from __future__ import annotations

import pytest

from pyenv_fridge.models import PackageInfo
from pyenv_fridge.package_managers.pip import PipPackageManager, parse_pip_freeze


# ---------------------------------------------------------------------------
# parse_pip_freeze
# ---------------------------------------------------------------------------


class TestParsePipFreeze:
    def test_basic_packages(self):
        output = "numpy==1.24.0\npandas==2.0.0\nrequests==2.31.0\n"
        packages = parse_pip_freeze(output)
        assert len(packages) == 3
        assert packages[0].name == "numpy"
        assert packages[0].version == "1.24.0"
        assert packages[0].install_method == "pip"
        assert packages[1].name == "pandas"
        assert packages[2].name == "requests"

    def test_empty_output(self):
        assert parse_pip_freeze("") == []

    def test_skips_comment_lines(self):
        output = "# These packages are installed.\nnumpy==1.24.0\n"
        packages = parse_pip_freeze(output)
        assert len(packages) == 1
        assert packages[0].name == "numpy"

    def test_skips_editable_installs(self):
        output = "-e git+https://github.com/example/repo.git@abc123#egg=mypackage\nnumpy==1.24.0\n"
        packages = parse_pip_freeze(output)
        assert len(packages) == 1
        assert packages[0].name == "numpy"

    def test_skips_requirements_references(self):
        output = "-r other.txt\n--index-url https://pypi.org/simple\nnumpy==1.24.0\n"
        packages = parse_pip_freeze(output)
        assert len(packages) == 1
        assert packages[0].name == "numpy"

    def test_skips_blank_lines(self):
        output = "\nnumpy==1.24.0\n\npandas==2.0.0\n"
        packages = parse_pip_freeze(output)
        assert len(packages) == 2

    def test_all_install_method_pip(self):
        output = "numpy==1.24.0\npandas==2.0.0\n"
        packages = parse_pip_freeze(output)
        assert all(p.install_method == "pip" for p in packages)

    def test_package_without_version(self):
        output = "some-package-without-version\n"
        packages = parse_pip_freeze(output)
        assert len(packages) == 1
        assert packages[0].name == "some-package-without-version"
        assert packages[0].version == ""

    def test_strips_whitespace(self):
        output = "  numpy==1.24.0  \n  pandas==2.0.0  \n"
        packages = parse_pip_freeze(output)
        assert packages[0].name == "numpy"
        assert packages[1].name == "pandas"

    def test_realistic_freeze_output(self):
        output = (
            "certifi==2024.2.2\n"
            "charset-normalizer==3.3.2\n"
            "idna==3.6\n"
            "numpy==1.26.4\n"
            "packaging==24.0\n"
            "pandas==2.2.1\n"
            "python-dateutil==2.9.0.post0\n"
            "pytz==2024.1\n"
            "requests==2.31.0\n"
            "six==1.16.0\n"
            "urllib3==2.2.1\n"
        )
        packages = parse_pip_freeze(output)
        assert len(packages) == 11
        names = [p.name for p in packages]
        assert "numpy" in names
        assert "requests" in names
        assert "pandas" in names


# ---------------------------------------------------------------------------
# PipPackageManager
# ---------------------------------------------------------------------------


class TestPipPackageManager:
    def test_name(self):
        pm = PipPackageManager()
        assert pm.name == "pip"

    def test_freeze_calls_subprocess(self, mocker):
        mock_run = mocker.patch("pyenv_fridge.package_managers.pip.subprocess.run")
        mock_run.return_value.stdout = "numpy==1.24.0\npandas==2.0.0\n"

        pm = PipPackageManager()
        packages = pm.freeze("/path/to/python")

        mock_run.assert_called_once()
        call_args = mock_run.call_args[0][0]
        assert "/path/to/python" in call_args
        assert "-m" in call_args
        assert "pip" in call_args
        assert "freeze" in call_args

        assert len(packages) == 2

    def test_install_packages_pip_only(self, mocker):
        mock_run = mocker.patch("pyenv_fridge.package_managers.pip.subprocess.run")
        pm = PipPackageManager()
        packages = [
            PackageInfo(name="numpy", version="1.24.0", install_method="pip"),
            PackageInfo(name="pandas", version="2.0.0", install_method="pip"),
        ]
        pm.install_packages("/path/to/python", packages)

        mock_run.assert_called_once()
        call_args = mock_run.call_args[0][0]
        assert "numpy==1.24.0" in call_args
        assert "pandas==2.0.0" in call_args

    def test_install_packages_skips_non_pip(self, mocker, capsys):
        mock_run = mocker.patch("pyenv_fridge.package_managers.pip.subprocess.run")
        pm = PipPackageManager()
        packages = [
            PackageInfo(name="numpy", version="1.24.0", install_method="pip"),
            PackageInfo(name="conda-pkg", version="1.0.0", install_method="conda"),
        ]
        pm.install_packages("/path/to/python", packages)

        call_args = mock_run.call_args[0][0]
        assert "numpy==1.24.0" in call_args
        assert "conda-pkg" not in call_args

        captured = capsys.readouterr()
        assert "conda-pkg" in captured.out
        assert "skip" in captured.out

    def test_install_packages_empty_list(self, mocker):
        mock_run = mocker.patch("pyenv_fridge.package_managers.pip.subprocess.run")
        pm = PipPackageManager()
        pm.install_packages("/path/to/python", [])
        mock_run.assert_not_called()

    def test_install_packages_no_version(self, mocker):
        mock_run = mocker.patch("pyenv_fridge.package_managers.pip.subprocess.run")
        pm = PipPackageManager()
        packages = [PackageInfo(name="mypackage", version="", install_method="pip")]
        pm.install_packages("/path/to/python", packages)
        call_args = mock_run.call_args[0][0]
        assert "mypackage" in call_args
        # Should not have "==" with empty version
        assert "mypackage==" not in call_args
