#!/usr/bin/env python3
"""NRT smoke render of an *installed* ChaosOsc with a real SuperCollider.

1. sclang runs WITHOUT --include-path, so the ChaosOsc class must compile
   from an Extensions directory sclang scans by itself. The script reports
   (to the post window and a small report file, which survives console
   buffering) Platform.userExtensionDir and the file ChaosOsc was compiled
   from, which must lie inside --plugin-dir, then writes a short NRT score
   that plays ChaosOsc.ar(3.9, 0.37). A missing class fails fast instead of
   leaving sclang waiting in its REPL.
2. scsynth renders that score in NRT mode (-N, -D 0, WAV float) with
   -U "<--plugin-dir><pathsep><built-in plugins dir>" (de-duplicated).
3. The render must be a finite, non-silent float32 WAV.

Used by .github/workflows/plugin-builds.yml (Windows, MSVC build) and by
tests/test_chaososc_cmake_install.py (macOS/Linux, isolated HOME).

Usage: python3 scripts/ci_nrt_smoke.py --sclang SCLANG --scsynth SCSYNTH
           --plugin-dir <Extensions>/ChaosOsc --work-dir DIR
           [--builtin-plugins DIR ...] [--expect-user-extension-dir DIR]
           [--report report.json]
"""

import argparse
import json
import math
import os
from pathlib import Path
import struct
import subprocess
import sys


SAMPLE_RATE = 48000
SCORE_SECONDS = 0.5
MIN_RMS = 0.005
SCORE_WRITTEN = "CHAOSOSC_SMOKE_SCORE_WRITTEN"
CLASS_MISSING = "CHAOSOSC_CLASS_MISSING"
EXTENSION_DIR_PREFIX = "CHAOSOSC_USER_EXTENSION_DIR="
CLASS_FILE_PREFIX = "CHAOSOSC_CLASS_FILE="


class SmokeTestError(Exception):
    """The installed plugin failed the NRT smoke test."""


def sc_path_literal(path, windows=None):
    """A SuperCollider string literal for `path`. Windows paths use forward
    slashes (which SuperCollider accepts) so no escaping is needed."""
    windows = os.name == "nt" if windows is None else windows
    text = str(path)
    if windows:
        text = text.replace("\\", "/")
    return '"' + text.replace("\\", "\\\\").replace('"', '\\"') + '"'


def build_bootstrap_source(main_path, report_path, windows=None):
    """sclang never exits on its own when a script fails to compile (it waits
    in its REPL), so check for the class at run time before compiling the
    score script that names ChaosOsc literally. Markers go to a report file
    as well as the post window, so they survive console buffering."""
    return """(
if('ChaosOsc'.asClass.isNil) {{
    File.use({report}, "w", {{ |file| file.write("{missing}" ++ Char.nl.asString) }});
    "{missing}: the ChaosOsc class is not in the compiled class library".postln;
    1.exit;
}};
thisProcess.interpreter.executeFile({main});
)
""".format(
        missing=CLASS_MISSING,
        report=sc_path_literal(report_path, windows),
        main=sc_path_literal(main_path, windows),
    )


def build_score_source(score_path, report_path, windows=None):
    # Symbols are written as 'quoted' literals and newlines as Char.nl so the
    # source stays free of backslashes on every platform.
    return """(
var scorePath = {score};
var def = SynthDef('chaosOscInstalledSmoke', {{
    Out.ar(0, ChaosOsc.ar(3.9, 0.37) * 0.1)
}});
var lines = [
    "{ext_prefix}" ++ Platform.userExtensionDir,
    "{class_prefix}" ++ ChaosOsc.filenameSymbol
];
Score([
    [0.0, ['d_recv', def.asBytes]],
    [0.01, ['s_new', 'chaosOscInstalledSmoke', 1000, 0, 0]],
    [{end}, ['c_set', 0, 0]]
]).writeOSCFile(scorePath);
lines = lines.add("{written}");
File.use({report}, "w", {{ |file|
    lines.do {{ |line| file.write(line ++ Char.nl.asString) }}
}});
lines.do {{ |line| line.postln }};
0.exit;
)
""".format(
        score=sc_path_literal(score_path, windows),
        report=sc_path_literal(report_path, windows),
        ext_prefix=EXTENSION_DIR_PREFIX,
        class_prefix=CLASS_FILE_PREFIX,
        end=SCORE_SECONDS,
        written=SCORE_WRITTEN,
    )


def normalized(path):
    return os.path.normcase(os.path.realpath(str(path)))


def is_within(path, directory):
    return normalized(path).startswith(normalized(directory) + os.sep)


def plugin_path_argument(paths):
    unique = []
    for path in paths:
        resolved = str(Path(path).resolve())
        if normalized(resolved) not in {normalized(item) for item in unique}:
            unique.append(resolved)
    return os.pathsep.join(unique)


def discover_builtin_plugin_dirs(scsynth):
    """The plugins directory shipped with scsynth: Contents/Resources/plugins
    in the macOS app, SuperCollider/plugins in the Windows zip, and
    <prefix>/lib/SuperCollider/plugins on Linux."""
    executable = Path(scsynth).resolve()
    for candidate in (
        executable.parent / "plugins",
        executable.parent.parent / "Resources" / "plugins",
        executable.parent.parent / "lib" / "SuperCollider" / "plugins",
    ):
        if candidate.is_dir():
            return [candidate.resolve()]
    return []


def read_float_wav(path):
    data = Path(path).read_bytes()
    if len(data) < 12 or data[:4] != b"RIFF" or data[8:12] != b"WAVE":
        raise SmokeTestError("{} is not a RIFF/WAVE file".format(path))
    fmt = samples = None
    offset = 12
    while offset + 8 <= len(data):
        name, size = struct.unpack_from("<4sI", data, offset)
        body = data[offset + 8 : offset + 8 + size]
        if name == b"fmt ":
            fmt = body
        elif name == b"data":
            samples = body
        offset += 8 + size + (size & 1)
    if fmt is None or samples is None or len(fmt) < 16:
        raise SmokeTestError("{} lacks a fmt or data chunk".format(path))
    format_code, channels, sample_rate = struct.unpack_from("<HHI", fmt)
    bits = struct.unpack_from("<H", fmt, 14)[0]
    if format_code == 0xFFFE and len(fmt) >= 40:
        format_code = struct.unpack_from("<I", fmt, 24)[0]
    if format_code != 3 or bits != 32:
        raise SmokeTestError(
            "{} is not float32 (format {}, {} bits)".format(path, format_code, bits)
        )
    if channels < 1 or len(samples) % (4 * channels):
        raise SmokeTestError("{} has misaligned sample data".format(path))
    values = struct.unpack("<{}f".format(len(samples) // 4), samples)
    return sample_rate, channels, values


def check_render(path, expected_channels=None, min_rms=MIN_RMS):
    sample_rate, channels, values = read_float_wav(path)
    if expected_channels is not None and channels != expected_channels:
        raise SmokeTestError(
            "{} has {} channels, expected {}".format(path, channels, expected_channels)
        )
    if not values:
        raise SmokeTestError("{} contains no samples".format(path))
    if not all(math.isfinite(value) for value in values):
        raise SmokeTestError("{} contains non-finite samples".format(path))
    rms = math.sqrt(sum(value * value for value in values) / len(values))
    if rms <= min_rms:
        raise SmokeTestError(
            "{} is silent or near-silent (rms {:.6f} <= {})".format(path, rms, min_rms)
        )
    return {
        "sample_rate": sample_rate,
        "channels": channels,
        "frames": len(values) // channels,
        "rms": rms,
        "peak": max(abs(value) for value in values),
    }


def run(command, timeout):
    print("==> {}".format(" ".join(str(part) for part in command)), flush=True)
    try:
        result = subprocess.run(
            [str(part) for part in command],
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as error:
        output = "".join(
            part.decode("utf-8", "replace") if isinstance(part, bytes) else part
            for part in (error.stdout, error.stderr)
            if part
        )
        raise SmokeTestError(
            "{} timed out after {} s:\n{}".format(command[0], timeout, output)
        )
    except OSError as error:
        raise SmokeTestError("could not run {}: {}".format(command[0], error))
    output = result.stdout + result.stderr
    print(output.rstrip(), flush=True)
    return result.returncode, output


def tagged_value(output, prefix):
    for line in output.splitlines():
        if line.startswith(prefix):
            return line[len(prefix) :].strip()
    return None


def resolve_program(program):
    path = Path(program)
    return str(path.resolve()) if path.is_file() else str(program)


def smoke_test(args):
    args.sclang = resolve_program(args.sclang)
    args.scsynth = resolve_program(args.scsynth)
    plugin_dir = Path(args.plugin_dir).resolve()
    work_dir = Path(args.work_dir).resolve()
    work_dir.mkdir(parents=True, exist_ok=True)
    bootstrap = work_dir / "chaososc_smoke.scd"
    score_source = work_dir / "chaososc_smoke_score.scd"
    sclang_report = work_dir / "chaososc_smoke_sclang.txt"
    score = work_dir / "chaososc_smoke.osc"
    render = work_dir / "chaososc_smoke.wav"
    for stale in (sclang_report, score, render):
        if stale.exists():
            stale.unlink()
    score_source.write_text(build_score_source(score, sclang_report), encoding="utf-8")
    bootstrap.write_text(
        build_bootstrap_source(score_source, sclang_report), encoding="utf-8"
    )

    sclang_command = [str(args.sclang), str(bootstrap)]
    status, output = run(sclang_command, args.timeout)
    report = (
        sclang_report.read_text(encoding="utf-8", errors="replace")
        if sclang_report.is_file()
        else ""
    )
    if CLASS_MISSING in report or CLASS_MISSING in output:
        raise SmokeTestError(
            "sclang did not compile the ChaosOsc class: it is not in an "
            "Extensions directory sclang scans (expected under {})".format(plugin_dir)
        )
    if status:
        raise SmokeTestError("sclang exited with status {}".format(status))
    if SCORE_WRITTEN not in report or not score.is_file():
        raise SmokeTestError("sclang did not write the NRT score {}".format(score))
    user_extension_dir = tagged_value(report, EXTENSION_DIR_PREFIX)
    class_file = tagged_value(report, CLASS_FILE_PREFIX)
    if not class_file or not is_within(class_file, plugin_dir):
        raise SmokeTestError(
            "sclang compiled ChaosOsc from {!r}, not from the installed {}".format(
                class_file, plugin_dir
            )
        )
    if args.expect_user_extension_dir and (
        not user_extension_dir
        or normalized(user_extension_dir) != normalized(args.expect_user_extension_dir)
    ):
        raise SmokeTestError(
            "Platform.userExtensionDir is {!r}, expected {}".format(
                user_extension_dir, args.expect_user_extension_dir
            )
        )

    builtin = [Path(path) for path in args.builtin_plugins] or discover_builtin_plugin_dirs(
        args.scsynth
    )
    if not builtin:
        raise SmokeTestError(
            "no built-in plugins directory found next to {}; pass "
            "--builtin-plugins".format(args.scsynth)
        )
    scsynth_command = [
        str(args.scsynth),
        "-U",
        plugin_path_argument([plugin_dir] + builtin),
        "-o",
        "1",
        "-z",
        "64",
        "-D",
        "0",
        "-N",
        str(score),
        "_",
        str(render),
        str(SAMPLE_RATE),
        "WAV",
        "float",
    ]
    status, output = run(scsynth_command, args.timeout)
    if status:
        raise SmokeTestError("scsynth exited with status {}".format(status))
    if "ChaosOsc" in output and ("not installed" in output or "not found" in output):
        raise SmokeTestError("scsynth could not find the ChaosOsc UGen")
    if not render.is_file():
        raise SmokeTestError("scsynth did not write {}".format(render))
    stats = check_render(render, expected_channels=1)
    if stats["sample_rate"] != SAMPLE_RATE:
        raise SmokeTestError("render sample rate is {}".format(stats["sample_rate"]))
    return {
        "sclang_command": sclang_command,
        "scsynth_command": scsynth_command,
        "user_extension_dir": user_extension_dir,
        "class_file": class_file,
        "render": str(render),
        "stats": stats,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--sclang", required=True)
    parser.add_argument("--scsynth", required=True)
    parser.add_argument("--plugin-dir", required=True)
    parser.add_argument("--work-dir", required=True)
    parser.add_argument("--builtin-plugins", action="append", default=[])
    parser.add_argument("--expect-user-extension-dir")
    parser.add_argument("--report")
    parser.add_argument("--timeout", type=float, default=300.0)
    args = parser.parse_args(argv)
    try:
        report = smoke_test(args)
    except SmokeTestError as error:
        print("ERROR: {}".format(error), file=sys.stderr)
        return 1
    if args.report:
        Path(args.report).write_text(json.dumps(report, indent=2), encoding="utf-8")
    stats = report["stats"]
    print(
        "ChaosOsc NRT smoke render OK: {} frames at {} Hz, rms {:.4f}, peak {:.4f} "
        "(class from {})".format(
            stats["frames"],
            stats["sample_rate"],
            stats["rms"],
            stats["peak"],
            report["class_file"],
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
