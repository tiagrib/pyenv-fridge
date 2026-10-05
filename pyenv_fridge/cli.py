"""Command-line interface for pyenv-fridge.

Usage examples
--------------

Put (save) all environments::

    fridge put

Put a single environment::

    fridge put myenv

Get (restore) an environment from its backup::

    fridge get myenv

Show diff between a backup and the currently activated environment::

    fridge diff myenv

List all stored backups::

    fridge list

Show / modify the current configuration::

    fridge config show
    fridge config set location /path/to/cloud/drive/pyenv-fridge
    fridge config set backend pyenv-virtualenv
"""

from __future__ import annotations

import argparse
import platform
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


def cmd_put(args: argparse.Namespace) -> int:
    """Handle the ``put`` sub-command (previously ``backup``)."""
    config = FridgeConfig.load()
    fridge = Fridge(config=config)
    dry_run: bool = getattr(args, "dry_run", False)

    if args.env_name:
        if dry_run:
            print(f"Collecting environment '{args.env_name}' (dry run) ...")
        else:
            print(f"Putting environment '{args.env_name}' in the fridge ...")
        try:
            if dry_run:
                backup = fridge.collect_env(args.env_name)
                print(
                    f"> Would save: {fridge._backup_path(args.env_name)}\n"
                    f"  Python {backup.python_version}, "
                    f"{len(backup.packages)} packages"
                )
            else:
                backup = fridge.backup_env(args.env_name)
                print(
                    f"[ok] Saved: {fridge._backup_path(args.env_name)}\n"
                    f"  Python {backup.python_version}, "
                    f"{len(backup.packages)} packages"
                )
        except Exception as exc:
            print(f"[error] Error: {exc}", file=sys.stderr)
            return 1
    else:
        if dry_run:
            print("Collecting all environments (dry run) ...")
        else:
            print("Putting all environments in the fridge ...")
        backups = fridge.backup_all(dry_run=dry_run)
        if dry_run:
            print(
                f"\nDry run complete. {len(backups)} environment(s) would be saved."
            )
        else:
            print(f"\n[ok] Done. {len(backups)} environment(s) backed up.")
        print(f"  Backup directory: {config.location}")

    return 0


def cmd_get(args: argparse.Namespace) -> int:
    """Handle the ``get`` sub-command (previously ``restore``)."""
    config = FridgeConfig.load()
    fridge = Fridge(config=config)

    no_deps = getattr(args, "force", False)
    python_version: Optional[str] = args.python or None
    print(f"Getting environment '{args.env_name}' from the fridge ...")
    if no_deps:
        print("  (--force: skipping dependency resolution)")
    if python_version:
        print(f"  (--python: using Python {python_version})")
    try:
        fridge.restore_env(
            args.env_name,
            create_if_missing=not args.no_create,
            reinstall=args.reinstall,
            no_deps=no_deps,
            python_version=python_version,
        )
    except FileNotFoundError as exc:
        print(f"[error] {exc}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"[error] Error during restore: {exc}", file=sys.stderr)
        return 1

    return 0


def cmd_activate(args: argparse.Namespace) -> int:
    """Handle the ``activate`` sub-command.

    Prints the path to the activate script for a given environment.
    Meant to be used with shell eval, e.g.:
        PowerShell:  fridge activate myenv | Invoke-Expression
        Bash:        eval "$(fridge activate myenv)"
    """
    from pyenv_fridge.backends import get_backend

    config = FridgeConfig.load()
    backend = get_backend(config.backend)
    env_name = args.env_name

    # Get the python executable path and derive the activate script location
    python_exe = Path(backend.get_python_executable(env_name))
    scripts_dir = python_exe.parent  # Scripts/ or bin/

    if sys.platform == "win32":
        activate_ps1 = scripts_dir / "Activate.ps1"
        activate_bat = scripts_dir / "activate.bat"
        if activate_ps1.exists():
            # Output PowerShell activation command
            print(f"& '{activate_ps1}'")
        elif activate_bat.exists():
            print(f'"{activate_bat}"')
        else:
            print(f"[error] No activate script found in {scripts_dir}", file=sys.stderr)
            return 1
    else:
        activate_sh = scripts_dir / "activate"
        if activate_sh.exists():
            print(f"source '{activate_sh}'")
        else:
            print(f"[error] No activate script found in {scripts_dir}", file=sys.stderr)
            return 1

    return 0


def cmd_update(args: argparse.Namespace) -> int:
    """Handle the ``update`` sub-command."""
    config = FridgeConfig.load()
    fridge = Fridge(config=config)

    env_name: Optional[str] = args.env_name or None
    from_version: Optional[str] = getattr(args, "from_version", None)
    to_version: str = args.to_version

    if env_name is None and from_version is None:
        print(
            "[error] Provide either an environment name or --from to select "
            "which backups to update.",
            file=sys.stderr,
        )
        return 1

    try:
        updated = fridge.update_python_version(
            to_version,
            env_name=env_name,
            from_version=from_version,
        )
    except FileNotFoundError as exc:
        print(f"[error] {exc}", file=sys.stderr)
        return 1

    if not updated:
        print("No backups were updated.")
    else:
        for backup in updated:
            print(f"  [ok] {backup.name} -> Python {to_version}")
        print(f"\n{len(updated)} backup(s) updated.")
    return 0


def cmd_diff(args: argparse.Namespace) -> int:
    """Handle the ``diff`` sub-command."""
    config = FridgeConfig.load()
    fridge = Fridge(config=config)

    current_python: Optional[str] = args.python or None

    try:
        diff = fridge.diff_env(args.env_name, current_python_executable=current_python)
    except FileNotFoundError as exc:
        print(f"[error] {exc}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"[error] Error: {exc}", file=sys.stderr)
        return 1

    print(f"Diff for '{args.env_name}'  (backup -> current):")
    print(diff.summary())
    return 0


def cmd_list(args: argparse.Namespace) -> int:
    """Handle the ``list`` sub-command."""
    config = FridgeConfig.load()
    fridge = Fridge(config=config)

    backups = fridge.list_backups()
    if not backups:
        print(f"No backups found in {config.location}")
        return 0

    print(f"Backups in {config.location}:\n")
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
        valid_keys = {"location", "backend", "package_manager"}
        if key not in valid_keys:
            print(
                f"[error] Unknown config key {key!r}. Valid keys: {', '.join(sorted(valid_keys))}",
                file=sys.stderr,
            )
            return 1
        if key == "location":
            config.location = Path(value)
        elif key == "backend":
            config.backend = value
        elif key == "package_manager":
            config.package_manager = value
        config.save()
        print(f"[ok] Set {key} = {value}")
        print(f"  Config saved to {config.config_path}")
        return 0

    print(f"[error] Unknown config sub-command: {sub!r}", file=sys.stderr)
    return 1


def _is_command_available(cmd: str) -> bool:
    """Check if a command is available on the system PATH."""
    try:
        subprocess.run(
            [cmd, "--version"],
            capture_output=True,
            text=True,
            check=True,
        )
        return True
    except (FileNotFoundError, subprocess.CalledProcessError):
        return False


def cmd_setup(args: argparse.Namespace) -> int:
    """Handle the ``setup`` sub-command."""
    config = FridgeConfig.load()
    install = getattr(args, "install", False)

    print("pyenv-fridge setup")
    print(f"  configured backend: {config.backend}")
    print(f"  configured package manager: {config.package_manager}")
    print()

    # -- uv availability check --
    uv_available = _is_command_available("uv")

    if config.backend == "uv" or config.package_manager == "uv":
        if uv_available:
            result = subprocess.run(
                ["uv", "--version"], capture_output=True, text=True
            )
            print(f"  uv: installed ({result.stdout.strip()})")
        else:
            print("  uv: NOT FOUND")
            if install:
                print("  installing uv ...")
                try:
                    if platform.system() == "Windows":
                        subprocess.run(
                            [
                                "powershell", "-ExecutionPolicy", "ByPass", "-c",
                                "irm https://astral.sh/uv/install.ps1 | iex",
                            ],
                            check=True,
                        )
                    else:
                        subprocess.run(
                            ["sh", "-c", "curl -LsSf https://astral.sh/uv/install.sh | sh"],
                            check=True,
                        )
                    print("  [ok] uv installed successfully.")
                    print("  You may need to restart your shell for uv to be on PATH.")
                    uv_available = True
                except Exception as exc:
                    print(f"  [error] uv installation failed: {exc}", file=sys.stderr)
                    return 1
            else:
                print("  run 'fridge setup --install' to install uv automatically.")
                print()
                print("  or install manually:")
                if platform.system() == "Windows":
                    print('    powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"')
                else:
                    print("    curl -LsSf https://astral.sh/uv/install.sh | sh")

    # -- Python availability via uv --
    if config.backend == "uv" and uv_available and install:
        print()
        print("  ensuring a Python version is available via uv ...")
        try:
            subprocess.run(
                ["uv", "python", "install"],
                check=True,
            )
            print("  [ok] Python is available.")
        except Exception as exc:
            print(f"  [error] Python installation failed: {exc}", file=sys.stderr)
            return 1

    # -- backend hints for non-uv backends --
    if config.backend == "pyenv-venv-win":
        print("  backend hint:")
        print("    Install pyenv-win-venv: https://github.com/pyenv-win/pyenv-win-venv")
    elif config.backend == "pyenv-virtualenv":
        print("  backend hint:")
        print("    Install pyenv-virtualenv: https://github.com/pyenv/pyenv-virtualenv")

    # -- pip bootstrap --
    if config.package_manager == "pip":
        print("  package manager: pip (bundled with Python)")
        if install:
            print("  bootstrapping pip via ensurepip ...")
            try:
                subprocess.run(
                    [sys.executable, "-m", "ensurepip", "--upgrade"],
                    check=True,
                )
                print("  [ok] pip bootstrap complete.")
            except Exception as exc:
                print(f"  [error] pip bootstrap failed: {exc}", file=sys.stderr)
                return 1

    print()
    print("[ok] Setup complete.")
    return 0


# ---------------------------------------------------------------------------
# Argument parser
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="fridge",
        description=(
            "pyenv-fridge -- backup and restore Python virtual environments.\n\n"
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

    # ---- put (formerly backup) ----
    put_parser = subparsers.add_parser(
        "put",
        aliases=["backup"],
        help="Save one or all virtual environments.",
        description=(
            "Capture the state of a virtual environment (Python version + "
            "installed packages) and save it as a JSON file."
        ),
    )
    put_parser.add_argument(
        "env_name",
        nargs="?",
        metavar="ENV",
        help="Name of the environment to save. Omit to save all environments.",
    )
    put_parser.add_argument(
        "--dry",
        action="store_true",
        default=False,
        help="Show what would be saved without writing any files.",
    )
    put_parser.set_defaults(func=cmd_put)

    # ---- get (formerly restore) ----
    get_parser = subparsers.add_parser(
        "get",
        aliases=["restore"],
        help="Restore a virtual environment from its backup.",
        description=(
            "Create the virtualenv (if it does not exist) and install the "
            "packages recorded in the backup snapshot."
        ),
    )
    get_parser.add_argument(
        "env_name",
        metavar="ENV",
        help="Name of the environment to restore.",
    )
    get_parser.add_argument(
        "--no-create",
        action="store_true",
        default=False,
        help="Do not create the env if it is missing; fail instead.",
    )
    get_parser.add_argument(
        "--reinstall",
        action="store_true",
        default=False,
        help="Reinstall packages even if the env already exists.",
    )
    get_parser.add_argument(
        "--force",
        action="store_true",
        default=False,
        help="Skip dependency resolution (install exact versions from backup).",
    )
    get_parser.add_argument(
        "--python",
        metavar="VERSION",
        default=None,
        help=(
            "Override the Python version to use when creating the environment "
            "(e.g. 3.12.0). Defaults to the version recorded in the backup."
        ),
    )
    get_parser.set_defaults(func=cmd_get)

    # ---- update ----
    update_parser = subparsers.add_parser(
        "update",
        help="Update the Python version in stored backups.",
        description=(
            "Change the Python version recorded in backup files. "
            "Use with an environment name to update a single backup, "
            "or with --from to bulk-update all backups matching a version."
        ),
    )
    update_parser.add_argument(
        "env_name",
        nargs="?",
        metavar="ENV",
        help="Name of the environment to update. Omit to update in bulk with --from.",
    )
    update_parser.add_argument(
        "--from",
        metavar="VERSION",
        dest="from_version",
        default=None,
        help="Only update backups whose Python version matches this value.",
    )
    update_parser.add_argument(
        "--to",
        metavar="VERSION",
        dest="to_version",
        required=True,
        help="The new Python version to set.",
    )
    update_parser.set_defaults(func=cmd_update)

    # ---- activate ----
    activate_parser = subparsers.add_parser(
        "activate",
        help="Print activation command for a virtual environment.",
        description=(
            "Print a shell command that activates the named environment.\n\n"
            "Usage:\n"
            "  PowerShell:  fridge activate myenv | Invoke-Expression\n"
            "  Bash:        eval \"$(fridge activate myenv)\"\n\n"
            "Or add a shell function to your profile for quick access:\n"
            "  PowerShell:  function fa { fridge activate $args[0] | Invoke-Expression }\n"
            "  Bash:        fa() { eval \"$(fridge activate $1)\"; }"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    activate_parser.add_argument(
        "env_name",
        metavar="ENV",
        help="Name of the environment to activate.",
    )
    activate_parser.set_defaults(func=cmd_activate)

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
        help="Check prerequisites and optionally install them.",
        description=(
            "Check that the configured backend and package manager are "
            "available. With --install, attempt to install missing tools "
            "(uv, Python, pip)."
        ),
    )
    setup_parser.add_argument(
        "--install",
        action="store_true",
        default=False,
        help="Install missing prerequisites (uv, Python, pip).",
    )
    # Keep old flag as hidden alias for backwards compatibility
    setup_parser.add_argument(
        "--install-package-manager",
        action="store_true",
        default=False,
        dest="install",
        help=argparse.SUPPRESS,
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
        help="Configuration key (location | backend | package_manager).",
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

    if args.command is None:
        print("~~~ fridge - keep your Python environments fresh ~~~")
        print()
        parser.print_usage()
        print()
        print("commands:")
        print("  put        Save Python virtual environments")
        print("  get        Restore environments from a backup")
        print("  update     Update Python version in stored backups")
        print("  activate   Print activation command for an env")
        print("  diff       Compare two backups side by side")
        print("  list       List all saved backups")
        print("  setup      Check and install prerequisites")
        print("  config     View or change configuration")
        print()
        return cmd_list(args)

    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
