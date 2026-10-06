#!/usr/bin/env python3
"""Verify a staged ChaosOsc install (`cmake --install <build> --prefix <stage>`)
the way CI does, on macOS, Linux, and Windows.

Checks <stage>/ChaosOsc/{ChaosOsc.scx|ChaosOsc.so, Classes/, HelpSource/},
that the plugin module is the only plugin binary in the staging tree, and that
it exports SuperCollider's C plugin entry points (`load`, `api_version`):
  macOS    `nm -gU` (every architecture slice) -> _load; with
           --require-universal, `lipo -info` must list arm64 and x86_64
  Linux    `nm -g --defined-only` -> load
  Windows  the PE export table (read directly) -> load in an x64 DLL, cross-
           checked with `dumpbin /exports` when Visual Studio provides it
           (--require-dumpbin makes that cross-check mandatory)
With --source-dir, Classes/ and HelpSource/ must mirror the source tree.

Usage: python3 scripts/ci_verify_plugin.py --staging-dir STAGE
           [--source-dir plugin/ChaosOsc] [--require-universal] [--require-dumpbin]
"""

import argparse
import filecmp
import glob
import os
from pathlib import Path
import re
import shutil
import struct
import subprocess
import sys


PLUGIN_NAME = "ChaosOsc"
REQUIRED_EXPORTS = ("load", "api_version")
PLUGIN_SUFFIXES = {".scx", ".so", ".dylib", ".dll"}
IMAGE_FILE_MACHINE_AMD64 = 0x8664
IGNORED_NAMES = {".DS_Store"}


class VerificationError(Exception):
    """The staged install does not meet the SuperCollider plugin contract."""


def plugin_binary_name(system=None):
    system = system or sys.platform
    if system == "darwin" or system.startswith("win") or system == "cygwin":
        return PLUGIN_NAME + ".scx"
    return PLUGIN_NAME + ".so"


def read_pe_exports(path):
    """Return (machine, exported names) from a PE/COFF DLL's export table."""
    data = Path(path).read_bytes()
    try:
        if data[:2] != b"MZ":
            raise VerificationError("{} is not a PE file (no MZ header)".format(path))
        pe_offset = struct.unpack_from("<I", data, 0x3C)[0]
        if data[pe_offset : pe_offset + 4] != b"PE\0\0":
            raise VerificationError("{} has no PE signature".format(path))
        coff = pe_offset + 4
        machine, section_count = struct.unpack_from("<HH", data, coff)
        optional_size = struct.unpack_from("<H", data, coff + 16)[0]
        optional = coff + 20
        magic = struct.unpack_from("<H", data, optional)[0]
        if magic == 0x20B:
            directories = optional + 112
        elif magic == 0x10B:
            directories = optional + 96
        else:
            raise VerificationError(
                "{} has an unknown optional header magic 0x{:x}".format(path, magic)
            )
        if struct.unpack_from("<I", data, directories - 4)[0] < 1:
            return machine, []
        export_rva = struct.unpack_from("<I", data, directories)[0]
        if export_rva == 0:
            return machine, []

        sections = []
        table = optional + optional_size
        for index in range(section_count):
            virtual_size, virtual_address, raw_size, raw_pointer = struct.unpack_from(
                "<IIII", data, table + 40 * index + 8
            )
            sections.append(
                (virtual_address, max(virtual_size, raw_size), raw_pointer)
            )

        def offset_of(rva):
            for virtual_address, size, raw_pointer in sections:
                if virtual_address <= rva < virtual_address + size:
                    return rva - virtual_address + raw_pointer
            raise VerificationError(
                "{}: RVA 0x{:x} is outside every section".format(path, rva)
            )

        directory = offset_of(export_rva)
        name_count = struct.unpack_from("<I", data, directory + 24)[0]
        names_rva = struct.unpack_from("<I", data, directory + 32)[0]
        names = []
        if name_count:
            name_table = offset_of(names_rva)
            for index in range(name_count):
                start = offset_of(struct.unpack_from("<I", data, name_table + 4 * index)[0])
                names.append(data[start : data.index(b"\0", start)].decode("ascii"))
        return machine, names
    except (struct.error, ValueError, UnicodeDecodeError) as error:
        raise VerificationError("{} is not a valid PE DLL: {}".format(path, error))


def parse_dumpbin_exports(text):
    """Exported names from `dumpbin /exports` output."""
    names = []
    in_table = False
    for line in text.splitlines():
        if re.match(r"^\s*ordinal\s+hint\s+RVA\s+name\s*$", line):
            in_table = True
            continue
        if not in_table:
            continue
        match = re.match(r"^\s*\d+\s+[0-9A-Fa-f]+\s+[0-9A-Fa-f]+\s+(\S+)", line)
        if match:
            names.append(match.group(1))
        elif line.strip() and names:
            break
    return names


def global_text_symbols_by_arch(nm_output):
    """{architecture: global text symbols} from `nm` output; single-arch
    output is keyed by the empty string."""
    symbols = {}
    arch = ""
    for line in nm_output.splitlines():
        header = re.search(r"\(for architecture (\S+)\):\s*$", line)
        if header:
            arch = header.group(1)
            symbols.setdefault(arch, set())
            continue
        fields = line.split()
        if len(fields) >= 3 and fields[-2] == "T":
            symbols.setdefault(arch, set()).add(fields[-1])
    return symbols


def global_text_symbols(nm_output):
    found = set()
    for names in global_text_symbols_by_arch(nm_output).values():
        found |= names
    return found


def run_tool(command):
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=120,
        )
    except (OSError, subprocess.SubprocessError) as error:
        raise VerificationError("could not run {}: {}".format(command[0], error))
    if result.returncode:
        raise VerificationError(
            "`{}` failed ({}):\n{}{}".format(
                " ".join(command), result.returncode, result.stdout, result.stderr
            )
        )
    return result.stdout


def find_dumpbin():
    found = shutil.which("dumpbin")
    if found or os.name != "nt":
        return found
    program_files = os.environ.get("ProgramFiles(x86)") or os.environ.get("ProgramFiles")
    if not program_files:
        return None
    vswhere = os.path.join(
        program_files, "Microsoft Visual Studio", "Installer", "vswhere.exe"
    )
    if not os.path.isfile(vswhere):
        return None
    installs = run_tool(
        [
            vswhere,
            "-latest",
            "-products",
            "*",
            "-requires",
            "Microsoft.VisualStudio.Component.VC.Tools.x86.x64",
            "-property",
            "installationPath",
        ]
    ).splitlines()
    for install in installs:
        candidates = sorted(
            glob.glob(
                os.path.join(
                    install.strip(),
                    "VC",
                    "Tools",
                    "MSVC",
                    "*",
                    "bin",
                    "Hostx64",
                    "x64",
                    "dumpbin.exe",
                )
            )
        )
        if candidates:
            return candidates[-1]
    return None


def verify_windows_exports(binary, require_dumpbin=False):
    machine, names = read_pe_exports(binary)
    if machine != IMAGE_FILE_MACHINE_AMD64:
        raise VerificationError(
            "{} is not an x64 (AMD64) DLL: machine 0x{:04x}".format(binary, machine)
        )
    missing = [name for name in REQUIRED_EXPORTS if name not in names]
    if missing:
        raise VerificationError(
            "{} does not export {} (exports: {})".format(
                binary, ", ".join(missing), ", ".join(sorted(names)) or "none"
            )
        )
    messages = ["PE export table (x64): {}".format(", ".join(sorted(names)))]
    dumpbin = find_dumpbin()
    if dumpbin:
        listing = run_tool([dumpbin, "/nologo", "/exports", str(binary)])
        dumpbin_names = parse_dumpbin_exports(listing)
        if "load" not in dumpbin_names:
            raise VerificationError(
                "dumpbin /exports does not list load:\n{}".format(listing)
            )
        messages.append("dumpbin /exports: {}".format(", ".join(dumpbin_names)))
    elif require_dumpbin:
        raise VerificationError(
            "dumpbin was not found on PATH or via vswhere (Visual Studio C++ tools)"
        )
    return messages


def verify_unix_exports(binary, system):
    if system == "darwin":
        listing = run_tool(["nm", "-gU", str(binary)])
        prefix = "_"
    else:
        listing = run_tool(["nm", "-g", "--defined-only", str(binary)])
        prefix = ""
    by_arch = global_text_symbols_by_arch(listing)
    if not by_arch:
        raise VerificationError("nm listed no global text symbols in {}".format(binary))
    messages = []
    for arch, names in sorted(by_arch.items()):
        missing = [prefix + name for name in REQUIRED_EXPORTS if prefix + name not in names]
        if missing:
            raise VerificationError(
                "{}{} does not export {} (global text symbols: {})".format(
                    binary,
                    " [{}]".format(arch) if arch else "",
                    ", ".join(missing),
                    ", ".join(sorted(names)) or "none",
                )
            )
        messages.append(
            "nm{}: {}".format(" [{}]".format(arch) if arch else "", ", ".join(sorted(names)))
        )
    return messages


def verify_universal(binary):
    info = run_tool(["lipo", "-info", str(binary)])
    archs = set(info.strip().rsplit(":", 1)[-1].split())
    missing = {"arm64", "x86_64"} - archs
    if missing:
        raise VerificationError(
            "{} is not universal: lipo reports {} (missing {})".format(
                binary, " ".join(sorted(archs)), " ".join(sorted(missing))
            )
        )
    return "lipo: {}".format(" ".join(sorted(archs)))


def relative_files(directory):
    return sorted(
        path.relative_to(directory).as_posix()
        for path in directory.rglob("*")
        if path.is_file() and path.name not in IGNORED_NAMES
    )


def verify_layout(staging_dir, system, source_dir=None):
    install_dir = staging_dir / PLUGIN_NAME
    if not install_dir.is_dir():
        raise VerificationError("{} does not exist".format(install_dir))
    binary = install_dir / plugin_binary_name(system)
    problems = []
    if not binary.is_file():
        problems.append("missing plugin module {}".format(binary))
    classes = install_dir / "Classes"
    if not classes.is_dir() or not any(classes.rglob("*.sc")):
        problems.append("missing Classes/ with the ChaosOsc .sc class file(s)")
    help_source = install_dir / "HelpSource"
    if not help_source.is_dir() or not any(help_source.rglob("*.schelp")):
        problems.append("missing HelpSource/ with .schelp help file(s)")
    extra = sorted(
        str(path)
        for path in staging_dir.rglob("*")
        if path.is_file() and path.suffix.lower() in PLUGIN_SUFFIXES and path != binary
    )
    if extra:
        problems.append("unexpected extra plugin binaries: {}".format(", ".join(extra)))
    if source_dir is not None:
        for name in ("Classes", "HelpSource"):
            source, installed = source_dir / name, install_dir / name
            if not installed.is_dir():
                continue
            if relative_files(source) != relative_files(installed) or any(
                not filecmp.cmp(source / item, installed / item, shallow=False)
                for item in relative_files(source)
            ):
                problems.append("{}/ does not mirror {}".format(installed, source))
    if problems:
        raise VerificationError("\n".join(problems))
    return binary


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--staging-dir", required=True)
    parser.add_argument("--source-dir")
    parser.add_argument("--require-universal", action="store_true")
    parser.add_argument("--require-dumpbin", action="store_true")
    args = parser.parse_args(argv)

    system = sys.platform
    staging_dir = Path(args.staging_dir).resolve()
    source_dir = Path(args.source_dir).resolve() if args.source_dir else None
    try:
        binary = verify_layout(staging_dir, system, source_dir)
        print("Verified install layout: {}".format(binary.parent))
        if system == "win32":
            messages = verify_windows_exports(binary, args.require_dumpbin)
        else:
            messages = verify_unix_exports(binary, system)
        if args.require_universal:
            messages.append(verify_universal(binary))
    except VerificationError as error:
        print("ERROR: {}".format(error), file=sys.stderr)
        return 1
    for message in messages:
        print("Verified {}".format(message))
    print("Verified exported plugin load symbol in {}".format(binary.name))
    return 0


if __name__ == "__main__":
    sys.exit(main())
