#!/usr/bin/env python3
"""Set up MaxxedBeats' isolated GitHub Copilot runtime for this user."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import tarfile
import tempfile
import urllib.error
import urllib.request
import venv

from bridge import BackendError, resolve_cli

SDK_VERSION = "1.0.16"
CLI_VERSION = "1.0.93"
# Checksums match the official Homebrew cask's pinned GitHub release assets.
CLI_RELEASE_SHA256 = {
    "darwin-arm64": "a003408e5b0aaa91c108fe911f4ba2cd5f052bbe34dd20e31c08b12a21ba6627",
    "darwin-x64": "f2885541970a656ef5dbf87043c9dc49d8e9203142ee015abc0f3d2ba6e2eae2",
    "linux-arm64": "d01fd18ba2489e7878d9ddcf46de9817a1a2f803b474c0283e2cfd8f837b5d22",
    "linux-x64": "23208bc3534d157031a3db3421e239169b2a67b98655862c0e1daa6d91afcea2",
}


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


def install_official_cli(install_directory, platform_name=None, architecture=None):
    platform_name = platform_name or sys.platform
    if platform_name == "darwin":
        release_platform = "darwin"
    elif platform_name.startswith("linux"):
        release_platform = "linux"
    else:
        raise SetupError("The pinned GitHub Copilot CLI release is not available for this operating system.")

    architecture = (architecture or platform.machine()).lower()
    release_architecture = {
        "aarch64": "arm64",
        "amd64": "x64",
        "arm64": "arm64",
        "x86_64": "x64",
    }.get(architecture)
    release_key = "{}-{}".format(release_platform, release_architecture)
    expected_sha256 = CLI_RELEASE_SHA256.get(release_key)
    if expected_sha256 is None:
        raise SetupError(
            "The pinned GitHub Copilot CLI release does not support this computer's processor architecture.")

    asset_name = "copilot-{}.tar.gz".format(release_key)
    url = "https://github.com/github/copilot-cli/releases/download/v{}/{}".format(
        CLI_VERSION, asset_name)
    install_directory = Path(install_directory)
    destination = install_directory / "copilot"
    try:
        install_directory.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix=".copilot-cli-", dir=str(install_directory)) as temporary:
            temporary_directory = Path(temporary)
            archive_path = temporary_directory / asset_name
            actual_sha256 = hashlib.sha256()
            try:
                with urllib.request.urlopen(url, timeout=60) as response, archive_path.open("wb") as archive_file:
                    while True:
                        chunk = response.read(1024 * 1024)
                        if not chunk:
                            break
                        actual_sha256.update(chunk)
                        archive_file.write(chunk)
            except (OSError, urllib.error.URLError, TimeoutError):
                raise SetupError(
                    "The pinned GitHub Copilot CLI release could not be downloaded. Check your internet connection and retry."
                ) from None

            if actual_sha256.hexdigest() != expected_sha256:
                raise SetupError(
                    "The GitHub Copilot CLI download failed its pinned checksum check and was not installed.")

            staged_executable = temporary_directory / "copilot"
            try:
                with tarfile.open(archive_path, "r:gz") as package:
                    member = package.getmember("copilot")
                    if not member.isfile():
                        raise SetupError(
                            "The pinned GitHub Copilot CLI archive did not contain a regular executable.")
                    source = package.extractfile(member)
                    if source is None:
                        raise SetupError(
                            "The pinned GitHub Copilot CLI archive could not be read.")
                    with source, staged_executable.open("wb") as executable:
                        shutil.copyfileobj(source, executable)
            except (KeyError, OSError, tarfile.TarError):
                raise SetupError(
                    "The pinned GitHub Copilot CLI archive could not be verified and was not installed.") from None

            staged_executable.chmod(0o755)
            os.replace(staged_executable, destination)
    except OSError:
        raise SetupError(
            "The private Copilot CLI could not be installed. Check disk space and folder permissions, then retry."
        ) from None
    return str(destination.absolute())


def resolve_cli_for_setup(cli_path=None, install_cli=False, platform_name=None,
                          install_directory=None, architecture=None):
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
    install_directory = install_directory or (runtime_directory(platform_name) / "cli")
    return install_official_cli(
        install_directory, platform_name=platform_name, architecture=architecture)


def setup_runtime(cli_path=None, *, install_cli=False, python_version=None,
                  settings_dir=None, runtime_dir=None):
    python_version = tuple(python_version or sys.version_info[:2])
    if python_version < (3, 11):
        raise SetupError("Copilot setup needs Python 3.11 or newer. Install Python 3.11+ and run setup again.")

    runtime_dir = Path(runtime_dir) if runtime_dir else runtime_directory()
    cli = resolve_cli_for_setup(
        cli_path, install_cli=install_cli, install_directory=runtime_dir / "cli")

    try:
        subprocess.run(
            [cli, "--version"], check=True, capture_output=True, text=True, timeout=15)
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
        raise SetupError(
            "The GitHub Copilot CLI could not be started. Install it from GitHub and run setup again."
        ) from None

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
        help="install the pinned, checksum-verified official CLI release if it is missing (macOS/Linux)")
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
