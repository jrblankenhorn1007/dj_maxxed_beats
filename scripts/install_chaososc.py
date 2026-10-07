#!/usr/bin/env python3
"""Build ChaosOsc with CMake and install it into SuperCollider's user
Extensions directory (or remove an installation made by this script).

Install:    python3 scripts/install_chaososc.py [--extensions-dir DIR]
                [--build-dir DIR] [--sc-path DIR] [--force] [--dry-run]
Uninstall:  python3 scripts/install_chaososc.py --uninstall
                [--extensions-dir DIR] [--dry-run]

The default Extensions directory matches SuperCollider 3.14.1's
`Platform.userExtensionDir`:
  macOS    ~/Library/Application Support/SuperCollider/Extensions
  Linux    ${XDG_DATA_HOME:-~/.local/share}/SuperCollider/Extensions
  Windows  %LOCALAPPDATA%\\SuperCollider\\Extensions
(SuperCollider also honors XDG_DATA_HOME on macOS, and so does this script.)

The plugin is configured, built (Release), and installed with
`cmake --install` into <Extensions>/ChaosOsc, which then holds a marker file.
An existing ChaosOsc folder without that marker is never replaced unless
--force is given, and --uninstall only ever removes a marked folder.
Requires CMake >= 3.16, a C++17 compiler, and Python 3 (stdlib only).
"""

import argparse
import datetime
import ntpath
import os
import posixpath
import re
import shutil
import stat
import subprocess
import sys


REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PLUGIN_SOURCE_DIR = os.path.join(REPO_ROOT, "plugin", "ChaosOsc")
DEFAULT_BUILD_DIR = os.path.join(PLUGIN_SOURCE_DIR, "build")
PLUGIN_NAME = "ChaosOsc"
MARKER_NAME = ".chaososc-install-marker"
MIN_CMAKE_VERSION = (3, 16)
BUILD_CONFIG = "Release"

CMAKE_INSTALL_HINT = (
    "Install CMake {}.{} or newer and re-run: macOS `brew install cmake` (or "
    "https://cmake.org/download/), Linux `sudo apt install cmake` (or your "
    "distribution's package), Windows `winget install Kitware.CMake` (Visual "
    "Studio's C++ workload also bundles CMake)."
).format(*MIN_CMAKE_VERSION)
COMPILER_HINT = (
    "a C++17 compiler is required: macOS `xcode-select --install`; Linux "
    "`sudo apt install build-essential` (or your distribution's g++/clang); "
    "Windows: Visual Studio 2022 or newer (or its Build Tools) with the "
    "\"Desktop development with C++\" workload"
)
NEXT_STEPS_INSTALL = """\
Next steps:
  1. Recompile the SuperCollider class library: in SCIDE choose
     Language > Recompile Class Library, or evaluate `thisProcess.recompile`.
  2. Reboot the audio server so it loads the new plugin: `s.reboot`
  3. Smoke test: { LeakDC.ar(ChaosOsc.ar(3.9, 0.37)) * 0.1 ! 2 }.play"""
NEXT_STEPS_UNINSTALL = """\
Next steps:
  1. Recompile the SuperCollider class library: in SCIDE choose
     Language > Recompile Class Library, or evaluate `thisProcess.recompile`.
  2. Reboot the audio server so it unloads the plugin: `s.reboot`"""


class InstallerError(Exception):
    """A failure with an actionable message for the user."""


def plugin_binary_name(system=None):
    system = system or sys.platform
    if system == "darwin" or system.startswith("win") or system == "cygwin":
        return PLUGIN_NAME + ".scx"
    return PLUGIN_NAME + ".so"


def default_extensions_dir(system=None, environ=None):
    """Mirror SuperCollider 3.14.1's Platform.userExtensionDir for `system`
    (a sys.platform value) using the given environment mapping."""
    system = system or sys.platform
    environ = os.environ if environ is None else environ
    if system == "win32":
        local_app_data = environ.get("LOCALAPPDATA")
        if not local_app_data:
            profile = environ.get("USERPROFILE")
            if not profile:
                raise InstallerError(
                    "cannot locate %LOCALAPPDATA% (neither LOCALAPPDATA nor "
                    "USERPROFILE is set); pass --extensions-dir explicitly"
                )
            local_app_data = ntpath.join(profile, "AppData", "Local")
        return ntpath.join(local_app_data, "SuperCollider", "Extensions")

    data_home = environ.get("XDG_DATA_HOME")
    if not data_home:
        home = environ.get("HOME")
        if not home:
            raise InstallerError(
                "cannot determine your home directory (HOME is not set); "
                "pass --extensions-dir explicitly"
            )
        if system == "darwin":
            data_home = posixpath.join(home, "Library", "Application Support")
        else:
            data_home = posixpath.join(home, ".local", "share")
    return posixpath.join(data_home, "SuperCollider", "Extensions")


def system_extension_dirs(system=None, environ=None):
    system = system or sys.platform
    environ = os.environ if environ is None else environ
    if system == "darwin":
        return ["/Library/Application Support/SuperCollider/Extensions"]
    if system == "win32":
        program_data = environ.get("PROGRAMDATA")
        if program_data:
            return [ntpath.join(program_data, "SuperCollider", "Extensions")]
        return []
    return [
        "/usr/local/share/SuperCollider/Extensions",
        "/usr/share/SuperCollider/Extensions",
    ]


def is_marked_install(path):
    return os.path.isfile(os.path.join(str(path), MARKER_NAME))


def absolute(path):
    return os.path.abspath(os.path.expanduser(str(path)))


def format_command(command):
    if os.name == "nt":
        return subprocess.list2cmdline(command)
    return " ".join(_quote(part) for part in command)


def _quote(part):
    if part and re.match(r"^[A-Za-z0-9_@%+=:,./-]+$", part):
        return part
    return "'" + part.replace("'", "'\"'\"'") + "'"


def find_cmake():
    cmake = shutil.which("cmake")
    if cmake is None:
        raise InstallerError(
            "CMake was not found on PATH. " + CMAKE_INSTALL_HINT
        )
    try:
        result = subprocess.run(
            [cmake, "--version"], capture_output=True, text=True, timeout=60
        )
    except (OSError, subprocess.SubprocessError) as error:
        raise InstallerError(
            "could not run {} ({}). {}".format(cmake, error, CMAKE_INSTALL_HINT)
        )
    match = re.search(r"cmake version (\d+)\.(\d+)", result.stdout)
    if result.returncode or not match:
        raise InstallerError(
            "`{} --version` failed:\n{}{}\n{}".format(
                cmake, result.stdout, result.stderr, CMAKE_INSTALL_HINT
            )
        )
    version = (int(match.group(1)), int(match.group(2)))
    if version < MIN_CMAKE_VERSION:
        raise InstallerError(
            "CMake {}.{} found at {}, but CMake {}.{} or newer is required. {}".format(
                version[0], version[1], cmake, *MIN_CMAKE_VERSION, CMAKE_INSTALL_HINT
            )
        )
    return cmake


def validate_sc_path(sc_path):
    sc_path = absolute(sc_path)
    header = os.path.join(sc_path, "include", "plugin_interface", "SC_PlugIn.hpp")
    if not os.path.isfile(header):
        raise InstallerError(
            "--sc-path {} is not a SuperCollider source root: {} does not "
            "exist. Pass the directory that contains include/plugin_interface "
            "and include/common, or omit --sc-path to use the pinned "
            "SuperCollider 3.14.1 plugin API headers.".format(sc_path, header)
        )
    return sc_path


def describe_existing(target, force):
    if not os.path.lexists(target):
        return "new install"
    if is_marked_install(target):
        return "replaces the previous installation made by this script"
    if force:
        return "replaces an existing folder NOT made by this script (--force)"
    raise InstallerError(
        "refusing to overwrite {}: it exists but has no {} marker, so it was "
        "not installed by this script. Remove or rename it yourself, or re-run "
        "with --force to replace it.".format(target, MARKER_NAME)
    )


def remove_path(path):
    if os.path.islink(path) or os.path.isfile(path):
        os.remove(path)
        return

    def make_writable_and_retry(function, failed_path, error):
        if isinstance(error, tuple):
            error = error[1]
        # Only Windows refuses to delete read-only files. On POSIX, deletion
        # depends on the parent directory, and chmod would follow symlinks
        # out of the install folder, so report the failure instead.
        if os.name != "nt" or os.path.islink(failed_path):
            raise error
        os.chmod(failed_path, stat.S_IWRITE)
        function(failed_path)

    if sys.version_info >= (3, 12):
        shutil.rmtree(path, onexc=make_writable_and_retry)
    else:
        shutil.rmtree(path, onerror=make_writable_and_retry)


def write_marker(target):
    stamp = datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0)
    with open(os.path.join(target, MARKER_NAME), "w", encoding="utf-8") as marker:
        marker.write(
            "ChaosOsc SuperCollider extension installed by "
            "scripts/install_chaososc.py.\n"
            "Re-running the installer may replace this folder, and "
            "`install_chaososc.py --uninstall` may remove it.\n"
            "source: {}\ninstalled: {}\n".format(PLUGIN_SOURCE_DIR, stamp.isoformat())
        )


def run_step(title, command, failure_message):
    print("==> {}: {}".format(title, format_command(command)), flush=True)
    try:
        result = subprocess.run(command)
    except OSError as error:
        raise InstallerError("{} ({})".format(failure_message, error))
    if result.returncode:
        raise InstallerError(
            "{} (exit status {}). See the output above.".format(
                failure_message, result.returncode
            )
        )


def find_duplicate_copies(extensions_dir, target):
    names = {"ChaosOsc.sc", "ChaosOsc.scx", "ChaosOsc.so"}
    target = os.path.normcase(os.path.realpath(target))
    roots = [extensions_dir] + system_extension_dirs()
    duplicates = []
    visited = set()
    for root in roots:
        if not os.path.isdir(root):
            continue
        # sclang and scsynth follow symlinked folders, so follow them too and
        # track real paths to stop at cycles.
        for directory, subdirectories, files in os.walk(root, followlinks=True):
            real = os.path.normcase(os.path.realpath(directory))
            if (
                real in visited
                or real == target
                or real.startswith(target + os.sep)
            ):
                subdirectories[:] = []
                continue
            visited.add(real)
            duplicates.extend(
                os.path.join(directory, name) for name in files if name in names
            )
    return sorted(duplicates)


def install(args):
    extensions_dir = absolute(args.extensions_dir or default_extensions_dir())
    target = os.path.join(extensions_dir, PLUGIN_NAME)
    build_dir = absolute(args.build_dir or DEFAULT_BUILD_DIR)
    sc_path = validate_sc_path(args.sc_path) if args.sc_path else ""
    plan = describe_existing(target, args.force)
    cmake = find_cmake()

    configure = [
        cmake,
        "-S",
        PLUGIN_SOURCE_DIR,
        "-B",
        build_dir,
        "-DCMAKE_BUILD_TYPE=" + BUILD_CONFIG,
        "-DSC_PATH=" + sc_path,
        # End-user builds should not fail on new compiler warnings; CI and
        # the repository tests build with warnings as errors.
        "-DCHAOSOSC_WARNINGS_AS_ERRORS=OFF",
    ]
    build = [
        cmake,
        "--build",
        build_dir,
        "--config",
        BUILD_CONFIG,
        "--target",
        PLUGIN_NAME,
        "--parallel",
    ]
    install_command = [
        cmake,
        "--install",
        build_dir,
        "--config",
        BUILD_CONFIG,
        "--prefix",
        extensions_dir,
    ]

    print("ChaosOsc installer{}".format(" (dry run)" if args.dry_run else ""))
    print("  Plugin source:     {}".format(PLUGIN_SOURCE_DIR))
    print("  Build directory:   {}".format(build_dir))
    print("  Extensions folder: {}".format(extensions_dir))
    print("  Install target:    {} ({})".format(target, plan))
    if args.dry_run:
        print("Commands that would run:")
        for command in (configure, build, install_command):
            print("  " + format_command(command))
        print("  then write the marker file {}".format(os.path.join(target, MARKER_NAME)))
        print("Dry run: nothing was built, installed, or removed.")
        return 0

    run_step(
        "Configuring",
        configure,
        "CMake configure failed. Check that " + COMPILER_HINT + "; and that "
        "raw.githubusercontent.com is reachable to fetch the pinned "
        "SuperCollider plugin API headers (or pass --sc-path <SuperCollider "
        "source root>)",
    )
    run_step(
        "Building",
        build,
        "ChaosOsc build failed. Fix the first compiler error shown above; if "
        "the build directory is stale, delete {} and retry".format(build_dir),
    )

    if os.path.lexists(target):
        remove_path(target)
    os.makedirs(target)
    # Marking first means an interrupted install can still be re-run or
    # removed with --uninstall without --force.
    write_marker(target)
    run_step(
        "Installing",
        install_command,
        "cmake --install failed. Check that {} is writable; re-running the "
        "installer replaces the partial install".format(extensions_dir),
    )

    binary = os.path.join(target, plugin_binary_name())
    missing = [
        path
        for path in (binary, os.path.join(target, "Classes"))
        if not os.path.exists(path)
    ]
    if missing:
        raise InstallerError(
            "the install is incomplete; missing: {}".format(", ".join(missing))
        )

    print("")
    print("ChaosOsc installed to: {}".format(target))
    for duplicate in find_duplicate_copies(extensions_dir, target):
        print(
            "WARNING: another ChaosOsc copy exists at {}; remove it, or sclang "
            "reports a duplicate class and scsynth may load the wrong "
            "plugin.".format(duplicate)
        )
    print(NEXT_STEPS_INSTALL)
    return 0


def uninstall(args):
    extensions_dir = absolute(args.extensions_dir or default_extensions_dir())
    target = os.path.join(extensions_dir, PLUGIN_NAME)
    if not os.path.lexists(target):
        print("Nothing to uninstall: {} does not exist.".format(target))
        return 0
    if not is_marked_install(target):
        raise InstallerError(
            "refusing to remove {}: it has no {} marker, so it was not "
            "installed by this script (--force does not apply to "
            "--uninstall). Remove it manually if you are sure it is "
            "ChaosOsc.".format(target, MARKER_NAME)
        )
    if args.dry_run:
        print("Dry run: would remove {} (installed by this script).".format(target))
        return 0
    remove_path(target)
    print("Removed ChaosOsc from: {}".format(target))
    print(NEXT_STEPS_UNINSTALL)
    return 0


def parse_args(argv):
    parser = argparse.ArgumentParser(
        description=(
            "Build the ChaosOsc SuperCollider plugin with CMake and install it "
            "into your SuperCollider user Extensions directory."
        )
    )
    parser.add_argument(
        "--extensions-dir",
        help="SuperCollider Extensions directory (default: {})".format(
            _safe_default_extensions_dir()
        ),
    )
    parser.add_argument(
        "--build-dir",
        help="CMake build directory (default: {})".format(DEFAULT_BUILD_DIR),
    )
    parser.add_argument(
        "--sc-path",
        help=(
            "SuperCollider source root to take the plugin API headers from "
            "(default: fetch the pinned SuperCollider 3.14.1 headers)"
        ),
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="print what would happen without building, installing, or removing",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="replace an existing ChaosOsc folder that this script did not install",
    )
    parser.add_argument(
        "--uninstall",
        action="store_true",
        help="remove a ChaosOsc folder previously installed by this script",
    )
    return parser.parse_args(argv)


def _safe_default_extensions_dir():
    try:
        return default_extensions_dir()
    except InstallerError:
        return "your SuperCollider user Extensions directory"


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
