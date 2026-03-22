"""Data models for pyenv-fridge backups."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class PackageInfo:
    """Represents a single installed package captured in a backup.

    Attributes:
        name: Package name (normalised to lower-case for comparisons).
        version: Installed version string (e.g. ``"1.24.0"``).
        install_method: How the package is installed. Currently ``"pip"`` or
            ``"conda"``.  Defaults to ``"pip"``.
        platform_notes: Optional mapping from platform key (``"windows"``,
            ``"linux"``, ``"darwin"``) to a free-text note, e.g. if the package
            requires a different install approach on a specific platform.

    Notes:
        Equality and hashing are based solely on the lower-cased package name
        so that package sets can be diffed with standard set operations.
    """

    name: str
    version: str
    install_method: str = "pip"
    platform_notes: Optional[Dict[str, str]] = None

    # ------------------------------------------------------------------
    # Serialisation helpers
    # ------------------------------------------------------------------

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {
            "name": self.name,
            "version": self.version,
            "install_method": self.install_method,
        }
        if self.platform_notes:
            d["platform_notes"] = self.platform_notes
        return d

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PackageInfo":
        return cls(
            name=data["name"],
            version=data["version"],
            install_method=data.get("install_method", "pip"),
            platform_notes=data.get("platform_notes"),
        )

    # ------------------------------------------------------------------
    # Comparison (name-only, case-insensitive)
    # ------------------------------------------------------------------

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, PackageInfo):
            return NotImplemented
        return self.name.lower() == other.name.lower()

    def __hash__(self) -> int:
        return hash(self.name.lower())

    def __repr__(self) -> str:
        return f"PackageInfo(name={self.name!r}, version={self.version!r}, install_method={self.install_method!r})"


@dataclass
class EnvBackup:
    """A complete backup snapshot of a single virtual environment.

    Attributes:
        name: Name of the virtual environment.
        python_version: Python version string (e.g. ``"3.11.5"``).
        packages: Ordered list of :class:`PackageInfo` objects captured via
            ``pip freeze``.
        created_at: ISO-8601 timestamp string of when the backup was taken.
        platform: OS platform key (``"windows"``, ``"linux"``, ``"darwin"``).
        backend: Virtualenv backend used (e.g. ``"pyenv-venv-win"``).
        package_manager: Package manager used (e.g. ``"pip"``).
    """

    name: str
    python_version: str
    packages: List[PackageInfo]
    created_at: str = field(
        default_factory=lambda: datetime.now(tz=timezone.utc).isoformat()
    )
    platform: str = ""
    backend: str = ""
    package_manager: str = "pip"

    # ------------------------------------------------------------------
    # Serialisation helpers
    # ------------------------------------------------------------------

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "python_version": self.python_version,
            "created_at": self.created_at,
            "platform": self.platform,
            "backend": self.backend,
            "package_manager": self.package_manager,
            "packages": [p.to_dict() for p in self.packages],
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "EnvBackup":
        return cls(
            name=data["name"],
            python_version=data["python_version"],
            packages=[PackageInfo.from_dict(p) for p in data.get("packages", [])],
            created_at=data.get("created_at", ""),
            platform=data.get("platform", ""),
            backend=data.get("backend", ""),
            package_manager=data.get("package_manager", "pip"),
        )

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)

    @classmethod
    def from_json(cls, json_str: str) -> "EnvBackup":
        return cls.from_dict(json.loads(json_str))

    @classmethod
    def from_file(cls, path: str) -> "EnvBackup":
        with open(path, "r", encoding="utf-8") as fh:
            return cls.from_json(fh.read())

    def save(self, path: str) -> None:
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(self.to_json())

    def packages_by_name(self) -> Dict[str, PackageInfo]:
        """Return packages indexed by lower-cased name."""
        return {p.name.lower(): p for p in self.packages}


@dataclass
class PackageDiff:
    """Difference in a single package between a backup and a live environment.

    Attributes:
        backup: The :class:`PackageInfo` as recorded in the backup.
        current: The :class:`PackageInfo` as found in the current environment.
    """

    backup: PackageInfo
    current: PackageInfo

    @property
    def version_changed(self) -> bool:
        return self.backup.version != self.current.version

    def __repr__(self) -> str:
        return (
            f"PackageDiff(name={self.backup.name!r}, "
            f"backup={self.backup.version!r}, current={self.current.version!r})"
        )


@dataclass
class EnvDiff:
    """Difference between a backup snapshot and a live virtual environment.

    Attributes:
        env_name: Name of the virtual environment being compared.
        backup_name: Name recorded in the backup (usually the same).
        added: Packages present in the *current* env but absent from the backup.
        removed: Packages present in the *backup* but absent from the current env.
        changed: Packages present in both but with differing versions.
    """

    env_name: str
    backup_name: str
    added: List[PackageInfo] = field(default_factory=list)
    removed: List[PackageInfo] = field(default_factory=list)
    changed: List[PackageDiff] = field(default_factory=list)

    @property
    def has_changes(self) -> bool:
        return bool(self.added or self.removed or self.changed)

    def summary(self) -> str:
        """Return a human-readable summary of the diff."""
        lines: List[str] = []
        if not self.has_changes:
            lines.append("No differences found.")
            return "\n".join(lines)
        if self.added:
            lines.append(f"Added ({len(self.added)}):")
            for p in sorted(self.added, key=lambda x: x.name.lower()):
                lines.append(f"  + {p.name}=={p.version}")
        if self.removed:
            lines.append(f"Removed ({len(self.removed)}):")
            for p in sorted(self.removed, key=lambda x: x.name.lower()):
                lines.append(f"  - {p.name}=={p.version}")
        if self.changed:
            lines.append(f"Changed ({len(self.changed)}):")
            for d in sorted(self.changed, key=lambda x: x.backup.name.lower()):
                lines.append(
                    f"  ~ {d.backup.name}: {d.backup.version} -> {d.current.version}"
                )
        return "\n".join(lines)
