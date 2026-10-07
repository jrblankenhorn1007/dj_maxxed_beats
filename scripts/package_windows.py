#!/usr/bin/env python3
"""Assemble MaxxedBeats-Windows-x64.zip: a ready-to-use Windows package that
needs no Python, CMake, or compiler on the user's PC.

    MaxxedBeats-Windows-x64/
      MaxxedBeats/    the Quark (extension/ plus agent/*.md in agent/)
      ChaosOsc/       the staged ChaosOsc extension folder (ChaosOsc.scx built
                      with MSVC, Classes/, HelpSource/, ...)
      install.ps1, uninstall.ps1, setup-copilot.ps1
      Install-MaxxedBeats.cmd, Setup-Copilot.cmd,
      Uninstall-MaxxedBeats.cmd, README.txt   (from scripts/windows/)

Usage (CI, after `cmake --install <build> --prefix <stage>`):
    python scripts/package_windows.py --chaososc-dir <stage>/ChaosOsc
        --output-dir build/package [--allow-non-windows-binary]

Writes <output-dir>/MaxxedBeats-Windows-x64/ and
<output-dir>/MaxxedBeats-Windows-x64.zip. Python 3.9+, stdlib only.
"""

import argparse
import os
from pathlib import Path
import shutil
import sys
import zipfile


ROOT = Path(__file__).resolve().parents[1]
PACKAGE_NAME = "MaxxedBeats-Windows-x64"
QUARK_SOURCE = ROOT / "extension"
AGENT_SOURCE = ROOT / "agent"
WINDOWS_FILES = ROOT / "scripts" / "windows"
TOP_LEVEL_FILES = (
    "install.ps1", "uninstall.ps1", "setup-copilot.ps1",
    "Install-MaxxedBeats.cmd", "Setup-Copilot.cmd",
    "Uninstall-MaxxedBeats.cmd", "README.txt",
)
IGNORED = shutil.ignore_patterns(".DS_Store", "__pycache__", "*.pyc", ".build",
                                 ".maxxedbeats-install-marker", ".chaososc-install-marker")
REQUIRED = (
    "MaxxedBeats/MaxxedBeats.quark",
    "MaxxedBeats/Classes/MaxxedBeats.sc",
    "MaxxedBeats/LaunchMaxxedBeats.scd",
    "MaxxedBeats/Data/windows/MaxxedBeatsCredential.ps1",
    "MaxxedBeats/Data/windows/MaxxedBeatsLaunch.ps1",
    "MaxxedBeats/Data/copilot/bridge.py",
    "MaxxedBeats/Data/copilot/requirements.txt",
    "MaxxedBeats/Data/copilot/setup_copilot.py",
    "MaxxedBeats/Data/copilot/setup-copilot.command",
    "MaxxedBeats/Data/copilot/setup-copilot.sh",
    "MaxxedBeats/agent/ROLE.md",
    "MaxxedBeats/agent/WORKFLOW.md",
    "MaxxedBeats/agent/SUPERCOLLIDER.md",
    "MaxxedBeats/agent/SAFETY.md",
    "ChaosOsc/ChaosOsc.scx",
    "ChaosOsc/Classes/ChaosOsc.sc",
    "install.ps1",
    "uninstall.ps1",
    "setup-copilot.ps1",
    "Install-MaxxedBeats.cmd",
    "Setup-Copilot.cmd",
    "Uninstall-MaxxedBeats.cmd",
    "README.txt",
)


class PackageError(Exception):
    pass


def is_pe_x64(path):
    """True when `path` is a PE image for x64 (IMAGE_FILE_MACHINE_AMD64)."""
    data = Path(path).read_bytes()[:4096]
    if data[:2] != b"MZ" or len(data) < 0x40:
        return False
    offset = int.from_bytes(data[0x3C:0x40], "little")
    if data[offset:offset + 4] != b"PE\0\0":
        return False
    return int.from_bytes(data[offset + 4:offset + 6], "little") == 0x8664


def assemble(chaososc_dir, output_dir, require_windows_binary=True):
    chaososc_dir = Path(chaososc_dir).resolve()
    output_dir = Path(output_dir).resolve()
    binary = chaososc_dir / "ChaosOsc.scx"
    if not binary.is_file():
        raise PackageError("no ChaosOsc.scx in {}".format(chaososc_dir))
    if require_windows_binary and not is_pe_x64(binary):
        raise PackageError("{} is not a Windows x64 DLL".format(binary))
    package = output_dir / PACKAGE_NAME
    if package.exists():
        shutil.rmtree(str(package))
    package.mkdir(parents=True)
    shutil.copytree(str(QUARK_SOURCE), str(package / "MaxxedBeats"), ignore=IGNORED)
    shutil.copytree(str(AGENT_SOURCE), str(package / "MaxxedBeats" / "agent"), ignore=IGNORED)
    shutil.copytree(str(chaososc_dir), str(package / "ChaosOsc"), ignore=IGNORED)
    for name in TOP_LEVEL_FILES:
        shutil.copy2(str(WINDOWS_FILES / name), str(package / name))
    missing = [name for name in REQUIRED if not (package / name).is_file()]
    if missing:
        raise PackageError("the package is incomplete: " + ", ".join(missing))
    archive = output_dir / (PACKAGE_NAME + ".zip")
    if archive.exists():
        archive.unlink()
    with zipfile.ZipFile(str(archive), "w", zipfile.ZIP_DEFLATED) as handle:
        for path in sorted(package.rglob("*")):
            if path.is_file():
                handle.write(str(path), str(path.relative_to(output_dir)).replace(os.sep, "/"))
    return package, archive


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--chaososc-dir", required=True,
                        help="staged ChaosOsc extension folder (contains ChaosOsc.scx)")
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--allow-non-windows-binary", action="store_true",
                        help="for tests on other systems only")
    args = parser.parse_args(argv)
    try:
        package, archive = assemble(args.chaososc_dir, args.output_dir,
                                    not args.allow_non_windows_binary)
    except PackageError as error:
        print("ERROR: " + str(error), file=sys.stderr)
        return 1
    print("Package folder: {}".format(package))
    print("Package zip:    {} ({} bytes)".format(archive, archive.stat().st_size))
    return 0


if __name__ == "__main__":
    sys.exit(main())
