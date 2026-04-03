"""Tests for pyenv_fridge.models."""

from __future__ import annotations

import json

import pytest

from pyenv_fridge.models import (
    EnvBackup,
    EnvDiff,
    PackageDiff,
    PackageInfo,
)


# ---------------------------------------------------------------------------
# PackageInfo
# ---------------------------------------------------------------------------


class TestPackageInfo:
    def test_basic_fields(self):
        pkg = PackageInfo(name="numpy", version="1.24.0")
        assert pkg.name == "numpy"
        assert pkg.version == "1.24.0"
        assert pkg.install_method == "pip"
        assert pkg.platform_notes is None

    def test_to_dict_minimal(self):
        pkg = PackageInfo(name="requests", version="2.31.0")
        d = pkg.to_dict()
        assert d == {"name": "requests", "version": "2.31.0", "install_method": "pip"}
        assert "platform_notes" not in d

    def test_to_dict_with_platform_notes(self):
        pkg = PackageInfo(
            name="pywin32",
            version="306",
            install_method="pip",
            platform_notes={"linux": "not available"},
        )
        d = pkg.to_dict()
        assert d["platform_notes"] == {"linux": "not available"}

    def test_from_dict_roundtrip(self):
        original = PackageInfo(
            name="pandas",
            version="2.0.0",
            install_method="pip",
            platform_notes={"windows": "ok"},
        )
        restored = PackageInfo.from_dict(original.to_dict())
        assert restored.name == original.name
        assert restored.version == original.version
        assert restored.install_method == original.install_method
        assert restored.platform_notes == original.platform_notes

    def test_from_dict_defaults(self):
        pkg = PackageInfo.from_dict({"name": "six", "version": "1.16.0"})
        assert pkg.install_method == "pip"
        assert pkg.platform_notes is None

    def test_equality_case_insensitive(self):
        a = PackageInfo(name="NumPy", version="1.24.0")
        b = PackageInfo(name="numpy", version="1.25.0")
        assert a == b  # equality is name-only

    def test_inequality_different_name(self):
        a = PackageInfo(name="numpy", version="1.24.0")
        b = PackageInfo(name="pandas", version="1.24.0")
        assert a != b

    def test_hash_case_insensitive(self):
        a = PackageInfo(name="NumPy", version="1.24.0")
        b = PackageInfo(name="numpy", version="1.25.0")
        assert hash(a) == hash(b)

    def test_set_deduplication(self):
        pkgs = {
            PackageInfo(name="NumPy", version="1.24.0"),
            PackageInfo(name="numpy", version="1.25.0"),
        }
        assert len(pkgs) == 1


# ---------------------------------------------------------------------------
# EnvBackup
# ---------------------------------------------------------------------------


class TestEnvBackup:
    def _make_backup(self) -> EnvBackup:
        return EnvBackup(
            name="myenv",
            python_version="3.11.5",
            packages=[
                PackageInfo(name="numpy", version="1.24.0"),
                PackageInfo(name="pandas", version="2.0.0"),
            ],
            platform="windows",
            backend="pyenv-venv-win",
            package_manager="pip",
        )

    def test_to_dict(self):
        backup = self._make_backup()
        d = backup.to_dict()
        assert d["name"] == "myenv"
        assert d["python_version"] == "3.11.5"
        assert d["platform"] == "windows"
        assert d["backend"] == "pyenv-venv-win"
        assert d["package_manager"] == "pip"
        assert len(d["packages"]) == 2
        assert d["packages"][0]["name"] == "numpy"

    def test_from_dict_roundtrip(self):
        backup = self._make_backup()
        restored = EnvBackup.from_dict(backup.to_dict())
        assert restored.name == backup.name
        assert restored.python_version == backup.python_version
        assert len(restored.packages) == 2
        assert restored.packages[0].name == "numpy"

    def test_to_json_from_json_roundtrip(self):
        backup = self._make_backup()
        json_str = backup.to_json()
        # Ensure it is valid JSON
        data = json.loads(json_str)
        assert data["name"] == "myenv"
        # Roundtrip
        restored = EnvBackup.from_json(json_str)
        assert restored.name == backup.name
        assert len(restored.packages) == len(backup.packages)

    def test_save_and_from_file(self, tmp_path):
        backup = self._make_backup()
        path = tmp_path / "myenv.json"
        backup.save(str(path))
        assert path.exists()
        loaded = EnvBackup.from_file(str(path))
        assert loaded.name == "myenv"
        assert loaded.python_version == "3.11.5"
        assert len(loaded.packages) == 2

    def test_packages_by_name(self):
        backup = self._make_backup()
        by_name = backup.packages_by_name()
        assert "numpy" in by_name
        assert "pandas" in by_name
        assert by_name["numpy"].version == "1.24.0"

    def test_created_at_set_automatically(self):
        backup = EnvBackup(name="test", python_version="3.10.0", packages=[])
        assert backup.created_at  # non-empty
        assert "T" in backup.created_at  # ISO-8601 format


# ---------------------------------------------------------------------------
# PackageDiff
# ---------------------------------------------------------------------------


class TestPackageDiff:
    def test_version_changed_true(self):
        d = PackageDiff(
            backup=PackageInfo(name="numpy", version="1.24.0"),
            current=PackageInfo(name="numpy", version="1.25.0"),
        )
        assert d.version_changed is True

    def test_version_changed_false(self):
        d = PackageDiff(
            backup=PackageInfo(name="numpy", version="1.24.0"),
            current=PackageInfo(name="numpy", version="1.24.0"),
        )
        assert d.version_changed is False


# ---------------------------------------------------------------------------
# EnvDiff
# ---------------------------------------------------------------------------


class TestEnvDiff:
    def test_has_changes_empty(self):
        diff = EnvDiff(env_name="myenv", backup_name="myenv")
        assert diff.has_changes is False

    def test_has_changes_with_added(self):
        diff = EnvDiff(env_name="myenv", backup_name="myenv")
        diff.added.append(PackageInfo(name="newpkg", version="1.0.0"))
        assert diff.has_changes is True

    def test_summary_no_changes(self):
        diff = EnvDiff(env_name="myenv", backup_name="myenv")
        assert "No differences" in diff.summary()

    def test_summary_with_changes(self):
        diff = EnvDiff(env_name="myenv", backup_name="myenv")
        diff.added.append(PackageInfo(name="newpkg", version="1.0.0"))
        diff.removed.append(PackageInfo(name="oldpkg", version="0.9.0"))
        diff.changed.append(
            PackageDiff(
                backup=PackageInfo(name="numpy", version="1.24.0"),
                current=PackageInfo(name="numpy", version="1.25.0"),
            )
        )
        summary = diff.summary()
        assert "Added" in summary
        assert "+ newpkg==1.0.0" in summary
        assert "Removed" in summary
        assert "- oldpkg==0.9.0" in summary
        assert "Changed" in summary
        assert "numpy" in summary
        assert "1.24.0" in summary
        assert "1.25.0" in summary
