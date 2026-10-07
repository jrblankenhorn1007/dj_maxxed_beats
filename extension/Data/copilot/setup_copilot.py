#!/usr/bin/env python3
"""Set up MaxxedBeats' isolated GitHub Copilot runtime for this user."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import venv

from bridge import BackendError, resolve_cli

SDK_VERSION = "1.0.16"


class SetupError(Exception):
    pass


def settings_directory(platform_name=None, home=None, environ=None):
    platform_name = platform_name or sys.platform
    home = Path.home() if home is None else Path(home)
    environ = os.environ if environ is None else environ
    if platform_name == "win32":
        base = Path(environ.get("APPDATA") or home / "AppData" / "Roaming")
        return base / "SuperCollider" / "MaxxedBeats"
    if platform_name == "darwin":
        base = Path(environ.get("XDG_CONFIG_HOME") or home / "Library" / "Application Support")
        return base / "SuperCollider" / "MaxxedBeats"
    if platform_name.startswith("linux"):
        base = Path(environ.get("XDG_CONFIG_HOME") or home / ".config")
        return base / "SuperCollider" / "MaxxedBeats"
    raise SetupError("MaxxedBeats Copilot setup does not support this operating system.")


def runtime_directory(platform_name=None, home=None, environ=None):
    platform_name = platform_name or sys.platform
    home = Path.home() if home is None else Path(home)
    environ = os.environ if environ is None else environ
    if platform_name == "win32":
        base = Path(environ.get("LOCALAPPDATA") or home / "AppData" / "Local")
    elif platform_name == "darwin":
        base = Path(environ.get("XDG_DATA_HOME") or home / "Library" / "Application Support")
    elif platform_name.startswith("linux"):
        base = Path(environ.get("XDG_DATA_HOME") or home / ".local" / "share")
    else:
        raise SetupError("MaxxedBeats Copilot setup does not support this operating system.")
    return base / "MaxxedBeats" / "Copilot"


def python_in_venv(venv_directory, platform_name=None):
    platform_name = platform_name or sys.platform
    venv_directory = Path(venv_directory)
    if platform_name == "win32":
        return venv_directory / "Scripts" / "python.exe"
    return venv_directory / "bin" / "python"


def resolve_cli_for_setup(cli_path=None, install_cli=False, platform_name=None):
    platform_name = platform_name or sys.platform
    spec = {"cli": cli_path} if cli_path else {}
    try:
        cli = resolve_cli(spec)
        if cli_path:
            return str(Path(cli_path).expanduser().absolute())
        return cli
    except BackendError as error:
        if not install_cli:
            raise SetupError(error.detail) from None
    if platform_name == "win32":
        raise SetupError("Run Setup-Copilot.cmd from the Windows MaxxedBeats package.")
    try:
        subprocess.run(
            ["bash", "-c", "curl -fsSL https://gh.io/copilot-install | bash"],
            check=True, timeout=300)
        return resolve_cli({})
    except (BackendError, OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
        raise SetupError(
            "The official GitHub Copilot CLI could not be installed. Check your internet connection and retry."
        ) from None


def setup_runtime(cli_path=None, *, install_cli=False, python_version=None,
                  settings_dir=None, runtime_dir=None):
    python_version = tuple(python_version or sys.version_info[:2])
    if python_version < (3, 11):
        raise SetupError("Copilot setup needs Python 3.11 or newer. Install Python 3.11+ and run setup again.")

    cli = resolve_cli_for_setup(cli_path, install_cli=install_cli)

    try:
        subprocess.run(
            [cli, "--version"], check=True, capture_output=True, text=True, timeout=15)
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
        raise SetupError(
            "The GitHub Copilot CLI could not be started. Install it from GitHub and run setup again."
        ) from None

    runtime_dir = Path(runtime_dir) if runtime_dir else runtime_directory()
    settings_dir = Path(settings_dir) if settings_dir else settings_directory()
    venv_directory = runtime_dir / "venv"
    try:
        venv_directory.parent.mkdir(parents=True, exist_ok=True)
        venv.EnvBuilder(with_pip=True).create(venv_directory)
    except OSError:
        raise SetupError("The private Copilot Python environment could not be created. Check disk space and retry.") from None
    python = python_in_venv(venv_directory)
    if not python.is_file():
        raise SetupError("Python could not create the private Copilot runtime. Run setup again.")

    requirements = Path(__file__).with_name("requirements.txt")
    try:
        subprocess.run(
            [str(python), "-m", "pip", "install", "--disable-pip-version-check",
             "-r", str(requirements)],
            check=True, capture_output=True, text=True, timeout=300)
        subprocess.run(
            [str(python), "-c",
             "from importlib.metadata import version; "
             "assert version('github-copilot-sdk') == '{}'".format(SDK_VERSION)],
            check=True, capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
        raise SetupError(
            "The Copilot SDK could not be installed. Check your internet connection and run setup again."
        ) from None

    configuration = {
        "pythonPath": str(python.absolute()),
        "cliPath": cli,
    }
    config_path = settings_dir / "copilot-runtime.json"
    temporary_path = None
    try:
        settings_dir.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
                mode="w", encoding="utf-8", prefix=".copilot-runtime-",
                suffix=".tmp", dir=settings_dir, delete=False) as handle:
            temporary_path = Path(handle.name)
            handle.write(json.dumps(configuration, indent=2) + "\n")
        if os.name != "nt":
            os.chmod(temporary_path, 0o600)
        os.replace(temporary_path, config_path)
    except OSError:
        if temporary_path is not None and temporary_path.exists():
            temporary_path.unlink()
        raise SetupError(
            "The Copilot runtime settings could not be saved. Check that your SuperCollider settings folder is writable."
        ) from None
    return configuration


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cli-path", help="use this official Copilot CLI executable")
    parser.add_argument(
        "--install-cli", action="store_true",
        help="install the official CLI with GitHub's installer if it is missing (macOS/Linux)")
    args = parser.parse_args(argv)
    try:
        setup_runtime(cli_path=args.cli_path, install_cli=args.install_cli)
    except SetupError as error:
        print("Copilot setup could not finish: {}".format(error), file=sys.stderr)
        return 1
    print("Copilot setup is complete.")
    print("In MaxxedBeats, choose GitHub Copilot, open Keys & Privacy, and click "
          "'Sign in to GitHub Copilot...'.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
