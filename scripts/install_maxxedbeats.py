#!/usr/bin/env python3
"""Install or remove the MaxxedBeats assistant: the MaxxedBeats Quark (GUI,
language classes, help, agent instructions) and the ChaosOsc server plugin,
together, in SuperCollider's user Extensions directory.

Install:    python3 scripts/install_maxxedbeats.py [--extensions-dir DIR]
                [--build-dir DIR] [--sc-path DIR] [--force] [--dry-run]
Uninstall:  python3 scripts/install_maxxedbeats.py --uninstall
                [--extensions-dir DIR] [--dry-run]

Default Extensions directory (SuperCollider 3.14.1 Platform.userExtensionDir):
  macOS    ~/Library/Application Support/SuperCollider/Extensions
  Linux    ${XDG_DATA_HOME:-~/.local/share}/SuperCollider/Extensions
  Windows  %LOCALAPPDATA%\\SuperCollider\\Extensions

The Quark is copied to <Extensions>/MaxxedBeats and ChaosOsc is built with
CMake and installed to <Extensions>/ChaosOsc by scripts/install_chaososc.py.
Each folder holds a marker file. A folder without its marker is never
replaced unless --force is given and is never removed by --uninstall. Both
folders are checked before anything is built, copied, or removed.
Requires Python 3.9+ (stdlib only); building ChaosOsc needs CMake >= 3.16
and a C++17 compiler (see install_chaososc.py).
"""

import argparse
import datetime
import os
import shutil
import sys


SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

import install_chaososc  # noqa: E402
from install_chaososc import InstallerError, absolute, default_extensions_dir  # noqa: E402,F401


REPO_ROOT = os.path.dirname(SCRIPT_DIR)
QUARK_SOURCE_DIR = os.path.join(REPO_ROOT, "extension")
AGENT_SOURCE_DIR = os.path.join(REPO_ROOT, "agent")
QUARK_NAME = "MaxxedBeats"
MARKER_NAME = ".maxxedbeats-install-marker"
REQUIRED_SOURCES = ("MaxxedBeats.quark", os.path.join("Classes", "MaxxedBeats.sc"))
IGNORED = shutil.ignore_patterns(".DS_Store", "__pycache__", "*.pyc", ".build")

NEXT_STEPS_INSTALL = """\
Next steps:
  1. Recompile the SuperCollider class library: in SCIDE choose
     Language > Recompile Class Library, or evaluate `thisProcess.recompile`.
  2. Reboot the audio server so it loads ChaosOsc: `s.reboot`
  3. Open the assistant: `MaxxedBeats.gui`
     (help: search the SCIDE help browser for "MaxxedBeats")."""
NEXT_STEPS_UNINSTALL = """\
Next steps:
  1. Close the MaxxedBeats window, then recompile the class library:
     Language > Recompile Class Library, or `thisProcess.recompile`.
  2. Reboot the audio server so it unloads ChaosOsc: `s.reboot`
  API keys stay in your OS credential store; remove them first from the
  assistant's Keys & Privacy tab if you no longer need them."""


class _NextStepsFilter:
    """Pass the ChaosOsc installer's output through, minus its own "Next
    steps" block, so the combined installer prints one set of instructions."""

    def __init__(self, stream):
        self.stream = stream
        self.suppressing = False
        self.pending = ""

    def write(self, text):
        self.pending += text
        while "\n" in self.pending:
            line, self.pending = self.pending.split("\n", 1)
            self._emit(line + "\n")
        return len(text)

    def _emit(self, line):
        if line.startswith("Next steps:"):
            self.suppressing = True
        elif self.suppressing and line.strip() and not line.startswith(" "):
            self.suppressing = False
        if not self.suppressing:
            self.stream.write(line)

    def flush(self):
        if self.pending:
            self._emit(self.pending)
            self.pending = ""
        self.stream.flush()


def _call_chaososc(function, args):
    real_stdout = sys.stdout
    filtered = _NextStepsFilter(real_stdout)
    sys.stdout = filtered
    try:
        return function(args)
    finally:
        filtered.flush()
        sys.stdout = real_stdout


def _plugin_args(args, extensions_dir):
    return argparse.Namespace(
        extensions_dir=extensions_dir,
        build_dir=args.build_dir,
        sc_path=args.sc_path,
        force=args.force,
        dry_run=args.dry_run,
        uninstall=args.uninstall,
    )


def is_marked_quark(path):
    return os.path.isfile(os.path.join(str(path), MARKER_NAME))


def describe_quark_target(target, force):
    if not os.path.lexists(target):
        return "new install"
    if is_marked_quark(target):
        return "replaces the previous installation made by this script"
    if force:
        return "replaces an existing folder NOT made by this script (--force)"
    raise InstallerError(
        "refusing to overwrite {}: it exists but has no {} marker, so it was not "
        "installed by this script. Remove or rename it yourself, or re-run with "
        "--force to replace it.".format(target, MARKER_NAME)
    )


def describe_plugin_target(target, force):
    try:
        return install_chaososc.describe_existing(target, force)
    except InstallerError as error:
        raise InstallerError("ChaosOsc plugin: {}".format(error))


def check_sources():
    missing = [
        os.path.join(QUARK_SOURCE_DIR, relative)
        for relative in REQUIRED_SOURCES
        if not os.path.isfile(os.path.join(QUARK_SOURCE_DIR, relative))
    ]
    if missing:
        raise InstallerError(
            "the MaxxedBeats sources are incomplete (missing {}); run the installer "
            "from a complete checkout".format(", ".join(missing))
        )


def write_marker(target):
    stamp = datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0)
    with open(os.path.join(target, MARKER_NAME), "w", encoding="utf-8") as marker:
        marker.write(
            "MaxxedBeats Quark installed by scripts/install_maxxedbeats.py.\n"
            "Re-running the installer may replace this folder, and "
            "`install_maxxedbeats.py --uninstall` may remove it.\n"
            "source: {}\ninstalled: {}\n".format(QUARK_SOURCE_DIR, stamp.isoformat())
        )


def install_quark(extensions_dir, force):
    """Copy the Quark (and agent instructions) into <extensions>/MaxxedBeats via
    a staging folder, so a failed copy never leaves a half-replaced install."""
    check_sources()
    target = os.path.join(extensions_dir, QUARK_NAME)
    describe_quark_target(target, force)
    staging = os.path.join(extensions_dir, ".{}.installing-{}".format(QUARK_NAME, os.getpid()))
    if os.path.lexists(staging):
        install_chaososc.remove_path(staging)
    os.makedirs(extensions_dir, exist_ok=True)
    try:
        shutil.copytree(QUARK_SOURCE_DIR, staging, ignore=IGNORED)
        if os.path.isdir(AGENT_SOURCE_DIR):
            shutil.copytree(AGENT_SOURCE_DIR, os.path.join(staging, "agent"), ignore=IGNORED)
        write_marker(staging)
        if os.path.lexists(target):
            install_chaososc.remove_path(target)
        os.rename(staging, target)
    finally:
        if os.path.lexists(staging):
            install_chaososc.remove_path(staging)
    return target


def find_duplicate_quarks(extensions_dir, target):
    duplicates = []
    target_real = os.path.normcase(os.path.realpath(target))
    roots = [extensions_dir] + install_chaososc.system_extension_dirs()
    visited = set()
    for root in roots:
        if not os.path.isdir(root):
            continue
        for directory, subdirectories, files in os.walk(root, followlinks=True):
            real = os.path.normcase(os.path.realpath(directory))
            if real in visited or real == target_real or real.startswith(target_real + os.sep):
                subdirectories[:] = []
                continue
            visited.add(real)
            if "MaxxedBeats.sc" in files:
                duplicates.append(os.path.join(directory, "MaxxedBeats.sc"))
    return sorted(duplicates)


def find_include_path_duplicates(extensions_dir):
    """sclang_conf.yaml lives next to Extensions; an include path that points
    at this checkout's extension folder would define every class twice."""
    config = os.path.join(os.path.dirname(extensions_dir), "sclang_conf.yaml")
    if not os.path.isfile(config):
        return config, []
    source = os.path.normcase(os.path.realpath(QUARK_SOURCE_DIR))
    hits = []
    with open(config, encoding="utf-8", errors="replace") as handle:
        for line in handle:
            entry = line.strip().lstrip("-").strip().strip("'\"")
            if not entry or entry.endswith(":"):
                continue
            real = os.path.normcase(os.path.realpath(os.path.expanduser(entry)))
            if real == source or real.startswith(source + os.sep):
                hits.append(entry)
    return config, hits


def install(args):
    extensions_dir = absolute(args.extensions_dir or default_extensions_dir())
    quark_target = os.path.join(extensions_dir, QUARK_NAME)
    plugin_target = os.path.join(extensions_dir, install_chaososc.PLUGIN_NAME)
    check_sources()
    quark_plan = describe_quark_target(quark_target, args.force)
    describe_plugin_target(plugin_target, args.force)

    print("MaxxedBeats installer{}".format(" (dry run)" if args.dry_run else ""))
    print("  Extensions folder: {}".format(extensions_dir))
    print("  Quark target:      {} ({})".format(quark_target, quark_plan))
    print("")
    print("== ChaosOsc plugin ==")
    _call_chaososc(install_chaososc.install, _plugin_args(args, extensions_dir))
    print("")
    print("== MaxxedBeats Quark ==")
    if args.dry_run:
        print("Would copy {} to {}".format(QUARK_SOURCE_DIR, quark_target))
        print("Would copy {} to {}".format(AGENT_SOURCE_DIR, os.path.join(quark_target, "agent")))
        print("Would write the marker file {}".format(os.path.join(quark_target, MARKER_NAME)))
        print("Dry run: nothing was built, installed, or removed.")
        return 0

    install_quark(extensions_dir, args.force)
    print("MaxxedBeats Quark installed to: {}".format(quark_target))
    for duplicate in find_duplicate_quarks(extensions_dir, quark_target):
        print(
            "WARNING: another MaxxedBeats copy exists at {}; remove it, or sclang "
            "reports duplicate classes.".format(duplicate)
        )
    config, entries = find_include_path_duplicates(extensions_dir)
    for entry in entries:
        print(
            "WARNING: {} includes {} (this checkout); remove that include path "
            "(Preferences > Interpreter, or Quarks) or sclang reports duplicate "
            "classes.".format(config, entry)
        )
    print("")
    print(NEXT_STEPS_INSTALL)
    return 0


def uninstall(args):
    extensions_dir = absolute(args.extensions_dir or default_extensions_dir())
    quark_target = os.path.join(extensions_dir, QUARK_NAME)
    plugin_target = os.path.join(extensions_dir, install_chaososc.PLUGIN_NAME)
    for target, marked in (
        (quark_target, is_marked_quark),
        (plugin_target, install_chaososc.is_marked_install),
    ):
        if os.path.lexists(target) and not marked(target):
            raise InstallerError(
                "refusing to uninstall: {} has no install marker, so it was not "
                "installed by this script. Nothing was removed; remove that folder "
                "manually if you are sure it belongs to MaxxedBeats.".format(target)
            )
    if not os.path.lexists(quark_target) and not os.path.lexists(plugin_target):
        print("Nothing to uninstall: neither {} nor {} exists.".format(quark_target, plugin_target))
        return 0

    if os.path.lexists(quark_target):
        if args.dry_run:
            print("Dry run: would remove {} (installed by this script).".format(quark_target))
        else:
            install_chaososc.remove_path(quark_target)
            print("Removed the MaxxedBeats Quark from: {}".format(quark_target))
    else:
        print("The MaxxedBeats Quark is not installed at {}.".format(quark_target))
    _call_chaososc(install_chaososc.uninstall, _plugin_args(args, extensions_dir))
    if not args.dry_run:
        print("")
        print(NEXT_STEPS_UNINSTALL)
    return 0


def parse_args(argv):
    parser = argparse.ArgumentParser(
        description=(
            "Install or remove the MaxxedBeats assistant (Quark + ChaosOsc plugin) "
            "in your SuperCollider user Extensions directory."
        )
    )
    parser.add_argument("--extensions-dir", help="SuperCollider Extensions directory "
                        "(default: Platform.userExtensionDir for this OS)")
    parser.add_argument("--build-dir", help="CMake build directory for ChaosOsc "
                        "(default: plugin/ChaosOsc/build)")
    parser.add_argument("--sc-path", help="SuperCollider source root for the plugin API "
                        "headers (default: the pinned SuperCollider 3.14.1 headers)")
    parser.add_argument("--dry-run", action="store_true",
                        help="print what would happen without building, copying, or removing")
    parser.add_argument("--force", action="store_true",
                        help="replace existing MaxxedBeats/ChaosOsc folders this script did not install")
    parser.add_argument("--uninstall", action="store_true",
                        help="remove the MaxxedBeats Quark and ChaosOsc installed by this script")
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    try:
        if args.uninstall:
            return uninstall(args)
        return install(args)
    except InstallerError as error:
        print("ERROR: {}".format(error), file=sys.stderr)
        return 1
    except OSError as error:
        print("ERROR: {}".format(error), file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("Interrupted.", file=sys.stderr)
        return 130


if __name__ == "__main__":
    sys.exit(main())
