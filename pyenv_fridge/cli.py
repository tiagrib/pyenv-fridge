"""Command-line interface for pyenv-fridge.

Usage examples
--------------

Backup all environments::

    fridge backup

Backup a single environment::

    fridge backup myenv

Restore an environment from its backup::

    fridge restore myenv

Show diff between a backup and the currently activated environment::

    fridge diff myenv

List all stored backups::

    fridge list

Show / modify the current configuration::

    fridge config show
    fridge config set backup_dir /path/to/cloud/drive/pyenv-fridge
    fridge config set backend pyenv-virtualenv
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path
from typing import List, Optional

from pyenv_fridge import __version__
from pyenv_fridge.config import FridgeConfig
from pyenv_fridge.fridge import Fridge


# ---------------------------------------------------------------------------
# Sub-command handlers
# ---------------------------------------------------------------------------


def cmd_backup(args: argparse.Namespace) -> int:
    """Handle the ``backup`` sub-command."""
    config = FridgeConfig.load()
    fridge = Fridge(config=config)

    if args.env_name:
        print(f"Backing up environment '{args.env_name}' …")
        try:
            backup = fridge.backup_env(args.env_name)
            print(
                f"✓ Backup saved: {fridge._backup_path(args.env_name)}\n"
                f"  Python {backup.python_version}, "
                f"{len(backup.packages)} packages"
            )
        except Exception as exc:
            print(f"✗ Error: {exc}", file=sys.stderr)
            return 1
    else:
        print("Backing up all environments …")
        backups = fridge.backup_all()
        print(f"\n✓ Done. {len(backups)} environment(s) backed up.")
        print(f"  Backup directory: {config.backup_dir}")

    return 0


def cmd_restore(args: argparse.Namespace) -> int:
    """Handle the ``restore`` sub-command."""
    config = FridgeConfig.load()
    fridge = Fridge(config=config)

    print(f"Restoring environment '{args.env_name}' …")
    try:
        fridge.restore_env(
            args.env_name,
            create_if_missing=not args.no_create,
            reinstall=args.reinstall,
        )
    except FileNotFoundError as exc:
        print(f"✗ {exc}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"✗ Error during restore: {exc}", file=sys.stderr)
        return 1

    return 0


def cmd_diff(args: argparse.Namespace) -> int:
    """Handle the ``diff`` sub-command."""
    config = FridgeConfig.load()
    fridge = Fridge(config=config)

    current_python: Optional[str] = args.python or None

    try:
        diff = fridge.diff_env(args.env_name, current_python_executable=current_python)
    except FileNotFoundError as exc:
        print(f"✗ {exc}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"✗ Error: {exc}", file=sys.stderr)
        return 1

    print(f"Diff for '{args.env_name}'  (backup → current):")
    print(diff.summary())
    return 0


def cmd_list(args: argparse.Namespace) -> int:
    """Handle the ``list`` sub-command."""
    config = FridgeConfig.load()
    fridge = Fridge(config=config)

    backups = fridge.list_backups()
    if not backups:
        print(f"No backups found in {config.backup_dir}")
        return 0

    print(f"Backups in {config.backup_dir}:\n")
    for backup in backups:
        print(
            f"  {backup.name:<30}  Python {backup.python_version:<10}  "
            f"{len(backup.packages):>4} packages  "
            f"[{backup.created_at[:19]}]"
        )
    return 0


def cmd_config(args: argparse.Namespace) -> int:
    """Handle the ``config`` sub-command."""
    config = FridgeConfig.load()

    sub = args.config_cmd

    if sub == "show" or sub is None:
        d = config.to_dict()
        print("pyenv-fridge configuration:")
        for key, value in d.items():
            print(f"  {key}: {value}")
        return 0

    if sub == "set":
        key: str = args.key
        value: str = args.value
        valid_keys = {"backup_dir", "backend", "package_manager"}
        if key not in valid_keys:
            print(
                f"✗ Unknown config key {key!r}. Valid keys: {', '.join(sorted(valid_keys))}",
                file=sys.stderr,
            )
            return 1
        if key == "backup_dir":
            config.backup_dir = Path(value)
        elif key == "backend":
            config.backend = value
        elif key == "package_manager":
            config.package_manager = value
        config.save()
        print(f"✓ Set {key} = {value}")
        print(f"  Config saved to {config.config_path}")
        return 0

    print(f"✗ Unknown config sub-command: {sub!r}", file=sys.stderr)
    return 1


def cmd_setup(args: argparse.Namespace) -> int:
    """Handle the ``setup`` sub-command."""
    config = FridgeConfig.load()
    print("Running pyenv-fridge setup …")
    print(f"  configured backend: {config.backend}")
    print(f"  configured package manager: {config.package_manager}")

    if config.backend == "pyenv-venv-win":
        print("  backend installer hint:")
        print(
            "    Install pyenv-win-venv: "
            "https://github.com/pyenv-win/pyenv-win-venv"
        )
    elif config.backend == "pyenv-virtualenv":
        print("  backend installer hint:")
        print(
            "    Install pyenv-virtualenv: "
            "https://github.com/pyenv/pyenv-virtualenv"
        )
    else:
        print("  backend installer hint:")
        print("    Custom backend configured; follow its own setup instructions.")

    if config.package_manager == "pip":
        print("  package manager check:")
        print("    pip is expected to be available with the selected Python envs.")
        if args.install_package_manager:
            print("  installing/upgrading pip via ensurepip …")
            try:
                subprocess.run(
                    [sys.executable, "-m", "ensurepip", "--upgrade"],
                    check=True,
                )
                print("  ✓ pip bootstrap complete.")
            except Exception as exc:
                print(f"  ✗ pip bootstrap failed: {exc}", file=sys.stderr)
                return 1
    else:
        print("  package manager check:")
        print(
            f"    package manager {config.package_manager!r} is custom; "
            "ensure it is installed and configured."
        )
        if args.install_package_manager:
            print(
                "  automatic installation is currently supported only for 'pip'.",
                file=sys.stderr,
            )
            return 1

    print("✓ Setup guidance complete.")
    return 0


# ---------------------------------------------------------------------------
# Argument parser
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="fridge",
        description=(
            "pyenv-fridge – backup and restore Python virtual environments.\n\n"
            "Snapshots are stored as JSON files in a configurable directory "
            "(default: ~/Documents/pyenv-fridge on Windows, "
            "~/.local/share/pyenv-fridge on Linux)."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--version", action="version", version=f"%(prog)s {__version__}"
    )

    subparsers = parser.add_subparsers(dest="command", metavar="<command>")
    subparsers.required = True

    # ---- backup ----
    backup_parser = subparsers.add_parser(
        "backup",
        help="Backup one or all virtual environments.",
        description=(
            "Capture the state of a virtual environment (Python version + "
            "pip freeze) and save it as a JSON file."
        ),
    )
    backup_parser.add_argument(
        "env_name",
        nargs="?",
        metavar="ENV",
        help="Name of the environment to back up. Omit to back up all environments.",
    )
    backup_parser.set_defaults(func=cmd_backup)

    # ---- restore ----
    restore_parser = subparsers.add_parser(
        "restore",
        help="Restore a virtual environment from its backup.",
        description=(
            "Create the virtualenv (if it does not exist) and install the "
            "packages recorded in the backup snapshot."
        ),
    )
    restore_parser.add_argument(
        "env_name",
        metavar="ENV",
        help="Name of the environment to restore.",
    )
    restore_parser.add_argument(
        "--no-create",
        action="store_true",
        default=False,
        help="Do not create the env if it is missing; fail instead.",
    )
    restore_parser.add_argument(
        "--reinstall",
        action="store_true",
        default=False,
        help="Reinstall packages even if the env already exists.",
    )
    restore_parser.set_defaults(func=cmd_restore)

    # ---- diff ----
    diff_parser = subparsers.add_parser(
        "diff",
        help="Show differences between a backup and the current environment.",
        description=(
            "Compare the packages in a stored backup against those currently "
            "installed in the named (or active) environment."
        ),
    )
    diff_parser.add_argument(
        "env_name",
        metavar="ENV",
        help="Name of the environment whose backup is used as reference.",
    )
    diff_parser.add_argument(
        "--python",
        metavar="PYTHON",
        default=None,
        help=(
            "Path to a Python interpreter to use as the 'current' environment. "
            "Defaults to the interpreter of ENV."
        ),
    )
    diff_parser.set_defaults(func=cmd_diff)

    # ---- list ----
    list_parser = subparsers.add_parser(
        "list",
        help="List all stored backups.",
    )
    list_parser.set_defaults(func=cmd_list)

    # ---- setup ----
    setup_parser = subparsers.add_parser(
        "setup",
        help="Show setup guidance for configured backend/package manager.",
        description=(
            "Print installation/setup instructions for the currently configured "
            "virtualenv backend and package manager."
        ),
    )
    setup_parser.add_argument(
        "--install-package-manager",
        action="store_true",
        default=False,
        help="Attempt to install/bootstrap the configured package manager (pip only).",
    )
    setup_parser.set_defaults(func=cmd_setup)

    # ---- config ----
    config_parser = subparsers.add_parser(
        "config",
        help="Show or modify pyenv-fridge configuration.",
    )
    config_sub = config_parser.add_subparsers(
        dest="config_cmd", metavar="<config-command>"
    )
    config_sub.add_parser("show", help="Print the current configuration.")
    set_parser = config_sub.add_parser("set", help="Update a configuration value.")
    set_parser.add_argument(
        "key",
        metavar="KEY",
        help="Configuration key (backup_dir | backend | package_manager).",
    )
    set_parser.add_argument(
        "value",
        metavar="VALUE",
        help="New value.",
    )
    config_parser.set_defaults(func=cmd_config)

    return parser


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
