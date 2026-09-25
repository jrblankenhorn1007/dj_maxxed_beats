#!/usr/bin/env python3
"""Render the procedural Chaos Garden composition with SuperCollider NRT."""

import argparse
import math
import os
from pathlib import Path
import shutil
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
COMPOSITION_SOURCE = ROOT / "examples" / "procedural_chaos_garden.scd"
CLASS_PATHS = (
    ROOT / "plugin" / "ChaosOsc" / "Classes",
    ROOT / "extension" / "Classes",
)
DEFAULT_PLUGIN_DIR = ROOT / "plugin" / "ChaosOsc" / "Tests" / ".build"
MAX_DURATION_SECONDS = 300.0


class RenderError(Exception):
    """An actionable error in the headless composition-render workflow."""


def resolve_executable(configured, fallback, label):
    if configured:
        candidate = Path(configured).expanduser()
        if not candidate.is_absolute():
            candidate = ROOT / candidate
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return str(candidate.resolve())
        resolved = shutil.which(configured)
        if resolved:
            return resolved
        raise RenderError(
            "{} does not name an executable file: {}".format(label, configured)
        )

    resolved = shutil.which(fallback)
    if resolved:
        return resolved
    raise RenderError(
        "{} is required; put it on PATH or set the {} environment variable."
        .format(fallback, label)
    )


def discover_builtin_plugins(scsynth):
    configured = os.environ.get("SC_DEFAULT_PLUGIN_PATH")
    if configured:
        candidates = [
            Path(entry).expanduser().resolve()
            for entry in configured.split(os.pathsep)
            if entry
        ]
        missing = [str(path) for path in candidates if not path.is_dir()]
        if missing:
            raise RenderError(
                "SC_DEFAULT_PLUGIN_PATH entries do not exist: {}".format(
                    ", ".join(missing)
                )
            )
    else:
        executable = Path(scsynth).resolve()
        candidates = (
            executable.parent / "Plugins",
            executable.parent.parent / "Resources" / "Plugins",
        )

    unique_paths = []
    seen = set()
    for path in candidates:
        resolved = path.resolve()
        if resolved.is_dir() and resolved not in seen:
            unique_paths.append(resolved)
            seen.add(resolved)
    if not unique_paths:
        raise RenderError(
            "could not locate SuperCollider's built-in Plugins directory; "
            "set SC_DEFAULT_PLUGIN_PATH to its path."
        )
    return unique_paths


def run_checked(command, environment, label, timeout):
    try:
        result = subprocess.run(
            command,
            cwd=ROOT,
            env=environment,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired as error:
        raise RenderError(
            "{} timed out after {} seconds.".format(label, timeout)
        ) from error
    if result.returncode:
        raise RenderError(
            "{} failed with exit code {}.\nstdout:\n{}\nstderr:\n{}".format(
                label, result.returncode, result.stdout, result.stderr
            )
        )
    return result


def parse_args(argv):
    parser = argparse.ArgumentParser(
        description=(
            "Write a deterministic stereo float32 WAV with sclang and "
            "scsynth's non-realtime renderer."
        )
    )
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="destination WAV path",
    )
    parser.add_argument(
        "--duration",
        type=float,
        default=9.0,
        help="render duration in seconds (4 to 300; default: 9)",
    )
    parser.add_argument(
        "--seed",
        type=float,
        default=0.37,
        help="reproducible ChaosOsc composition seed in (0, 1) (default: 0.37)",
    )
    parser.add_argument(
        "--sample-rate",
        type=int,
        default=48000,
        help="WAV sample rate in Hz (default: 48000)",
    )
    parser.add_argument(
        "--plugin-dir",
        type=Path,
        default=DEFAULT_PLUGIN_DIR,
        help="directory containing the built ChaosOsc.scx plugin",
    )
    parser.add_argument(
        "--sclang",
        default=os.environ.get("SCLANG"),
        help="sclang executable (defaults to SCLANG or PATH)",
    )
    parser.add_argument(
        "--scsynth",
        default=os.environ.get("SCSYNTH"),
        help="scsynth executable (defaults to SCSYNTH or PATH)",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=120,
        help="per-process timeout in seconds (default: 120)",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="replace an existing WAV or OSC score sidecar",
    )
    args = parser.parse_args(argv)

    if not math.isfinite(args.duration) or not (
        4.0 <= args.duration <= MAX_DURATION_SECONDS
    ):
        parser.error("--duration must be finite and between 4 and 300 seconds")
    if not math.isfinite(args.seed) or not (0.0 < args.seed < 1.0):
        parser.error("--seed must be finite and strictly between 0 and 1")
    if not (8000 <= args.sample_rate <= 192000):
        parser.error("--sample-rate must be between 8000 and 192000 Hz")
    if args.timeout < 1:
        parser.error("--timeout must be a positive integer")
    return args


def render(args):
    output_path = args.output.expanduser().resolve()
    score_path = output_path.with_name(output_path.name + ".osc")
    existing_outputs = [
        path for path in (output_path, score_path) if path.exists()
    ]
    if existing_outputs and not args.overwrite:
        raise RenderError(
            "refusing to overwrite existing output(s): {}. Choose a new "
            "--output path or pass --overwrite to replace them."
            .format(", ".join(str(path) for path in existing_outputs))
        )

    sclang = resolve_executable(args.sclang, "sclang", "SCLANG")
    scsynth = resolve_executable(args.scsynth, "scsynth", "SCSYNTH")
    plugin_dir = args.plugin_dir.expanduser().resolve()
    plugin_library = plugin_dir / "ChaosOsc.scx"
    if not plugin_library.is_file():
        raise RenderError(
            "ChaosOsc plugin not found at {}. Build it first with: "
            "bash plugin/ChaosOsc/Tests/build_plugin_smoke_test.sh"
            .format(plugin_library)
        )

    missing_class_paths = [str(path) for path in CLASS_PATHS if not path.is_dir()]
    if missing_class_paths:
        raise RenderError(
            "SuperCollider class path is missing: {}".format(
                ", ".join(missing_class_paths)
            )
        )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    environment = os.environ.copy()
    environment["SCLANG"] = sclang
    environment["SCSYNTH"] = scsynth
    sclang_command = [sclang]
    for class_path in CLASS_PATHS:
        sclang_command.extend(["--include-path", str(class_path)])
    sclang_command.extend(
        [
            str(COMPOSITION_SOURCE),
            str(score_path),
            format(args.duration, ".9g"),
            format(args.seed, ".9g"),
        ]
    )
    language_result = run_checked(
        sclang_command,
        environment,
        "sclang composition",
        args.timeout,
    )
    if (
        "MAXXED_BEATS_COMPOSITION_SCORE_WRITTEN"
        not in language_result.stdout + language_result.stderr
    ):
        raise RenderError(
            "sclang exited without confirming that it wrote the NRT score."
        )
    if not score_path.is_file():
        raise RenderError(
            "sclang reported success but did not write the NRT score: {}".format(
                score_path
            )
        )

    plugin_paths = [plugin_dir] + discover_builtin_plugins(scsynth)
    unique_plugin_paths = []
    seen = set()
    for path in plugin_paths:
        resolved = path.resolve()
        if resolved not in seen:
            unique_plugin_paths.append(resolved)
            seen.add(resolved)

    server_command = [
        scsynth,
        "-U",
        os.pathsep.join(str(path) for path in unique_plugin_paths),
        "-o",
        "2",
        "-z",
        "64",
        "-D",
        "0",
        "-N",
        str(score_path),
        "_",
        str(output_path),
        str(args.sample_rate),
        "WAV",
        "float",
    ]
    run_checked(server_command, environment, "scsynth NRT render", args.timeout)
    if not output_path.is_file() or output_path.stat().st_size < 44:
        raise RenderError(
            "scsynth exited successfully but did not write a valid-sized WAV: "
            "{}".format(output_path)
        )
    return output_path, score_path


def main(argv=None):
    args = parse_args(argv)
    try:
        output_path, score_path = render(args)
    except (OSError, RenderError) as error:
        print("Render failed: {}".format(error), file=sys.stderr)
        return 1

    print(
        "Wrote stereo float32 WAV: {} ({} Hz, {:.3f} seconds, seed {})".format(
            output_path, args.sample_rate, args.duration, args.seed
        )
    )
    print("Retained NRT score: {}".format(score_path))
    return 0


if __name__ == "__main__":
    sys.exit(main())
