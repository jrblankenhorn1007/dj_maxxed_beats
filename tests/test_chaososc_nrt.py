import math
import os
from pathlib import Path
import shutil
import struct
import subprocess
import unittest


ROOT = Path(__file__).resolve().parents[1]
TEST_DIR = ROOT / "tests"
BUILD_DIR = TEST_DIR / ".build"
SCORE_SOURCE = TEST_DIR / "chaososc_nrt_score.scd"
OSC_SCORE = BUILD_DIR / "chaososc_nrt.osc"
PLUGIN_BUILD_SCRIPT = (
    ROOT / "plugin" / "ChaosOsc" / "Tests" / "build_plugin_smoke_test.sh"
)
PLUGIN_BUILD_DIR = ROOT / "plugin" / "ChaosOsc" / "Tests" / ".build"
PLUGIN_LIBRARY = PLUGIN_BUILD_DIR / "ChaosOsc.scx"
SAMPLE_RATE = 48000
BLOCK_SIZE = 64
DURATION_SECONDS = 1.0
CONTROL_CHANGE_SECONDS = 0.5


def resolve_executable(environment_name, executable_name):
    configured = os.environ.get(environment_name)
    if configured:
        candidate = Path(configured)
        if not candidate.is_absolute():
            candidate = ROOT / candidate
        if candidate.is_file():
            return str(candidate.resolve())
        resolved = shutil.which(configured)
        if resolved:
            return resolved
        raise AssertionError(
            "{} does not name an executable file: {}".format(
                environment_name, configured
            )
        )

    resolved = shutil.which(executable_name)
    if resolved:
        return resolved
    raise AssertionError(
        "{} is required (or set {})".format(executable_name, environment_name)
    )


def run_checked(command, environment, timeout=120):
    result = subprocess.run(
        command,
        cwd=ROOT,
        env=environment,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    if result.returncode:
        raise AssertionError(
            "command failed ({}):\n{}\n{}".format(
                result.returncode, result.stdout, result.stderr
            )
        )
    return result


def read_float_wav(path):
    data = path.read_bytes()
    if len(data) < 12 or data[:4] != b"RIFF" or data[8:12] != b"WAVE":
        raise AssertionError("render is not a RIFF/WAVE file")

    format_chunk = None
    sample_chunk = None
    offset = 12
    while offset + 8 <= len(data):
        chunk_name, chunk_size = struct.unpack_from("<4sI", data, offset)
        chunk_start = offset + 8
        chunk_end = chunk_start + chunk_size
        if chunk_end > len(data):
            raise AssertionError("WAV chunk extends beyond the file")
        chunk = data[chunk_start:chunk_end]
        if chunk_name == b"fmt ":
            format_chunk = chunk
        elif chunk_name == b"data":
            sample_chunk = chunk
        offset = chunk_end + (chunk_size & 1)

    if format_chunk is None or sample_chunk is None or len(format_chunk) < 16:
        raise AssertionError("WAV is missing its format or audio-data chunk")

    (
        format_code,
        channels,
        sample_rate,
        _byte_rate,
        _block_align,
        bits_per_sample,
    ) = struct.unpack_from("<HHIIHH", format_chunk)
    if format_code == 0xFFFE and len(format_chunk) >= 40:
        format_code = struct.unpack_from("<I", format_chunk, 24)[0]
    if format_code != 3 or bits_per_sample != 32:
        raise AssertionError(
            "expected IEEE float32 WAV, got format {} with {} bits".format(
                format_code, bits_per_sample
            )
        )
    if channels < 1 or sample_rate < 1 or len(sample_chunk) % 4:
        raise AssertionError("WAV has invalid channel, rate, or sample data")

    sample_count = len(sample_chunk) // 4
    if sample_count % channels:
        raise AssertionError("WAV sample count is not aligned to its channels")
    samples = struct.unpack("<{}f".format(sample_count), sample_chunk)
    frames = [
        tuple(samples[index : index + channels])
        for index in range(0, sample_count, channels)
    ]
    return sample_rate, channels, bits_per_sample, frames


def max_channel_difference(frames, left, right, start=0, end=None):
    end = len(frames) if end is None else end
    return max(
        abs(frames[index][left] - frames[index][right])
        for index in range(start, end)
    )


def channel_rms(frames, channel):
    total = sum(frame[channel] * frame[channel] for frame in frames)
    return math.sqrt(total / len(frames))


def discover_builtin_plugins(scsynth):
    configured = os.environ.get("SC_DEFAULT_PLUGIN_PATH")
    if configured:
        paths = [
            (ROOT / path).resolve() if not Path(path).is_absolute() else Path(path)
            for path in configured.split(os.pathsep)
        ]
        missing = [str(path) for path in paths if not path.is_dir()]
        if missing:
            raise AssertionError(
                "SC_DEFAULT_PLUGIN_PATH entries do not exist: {}".format(
                    ", ".join(missing)
                )
            )
        candidates = paths
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
    return unique_paths


class ChaosOscNRTIntegrationTests(unittest.TestCase):
    def test_plugin_class_nrt_render_and_control_rate_contract(self):
        sclang = resolve_executable("SCLANG", "sclang")
        scsynth = resolve_executable("SCSYNTH", "scsynth")
        BUILD_DIR.mkdir(parents=True, exist_ok=True)

        environment = os.environ.copy()
        runtime_home = BUILD_DIR / "runtime-home"
        runtime_temp = BUILD_DIR / "runtime-tmp"
        runtime_home.mkdir(parents=True, exist_ok=True)
        runtime_temp.mkdir(parents=True, exist_ok=True)
        environment.update(
            {
                "HOME": str(runtime_home),
                "TMPDIR": str(runtime_temp),
                "XDG_CONFIG_HOME": str(runtime_home / ".config"),
                "XDG_DATA_HOME": str(runtime_home / ".local" / "share"),
            }
        )

        build_result = run_checked(
            ["bash", str(PLUGIN_BUILD_SCRIPT)], environment, timeout=180
        )
        self.assertTrue(
            PLUGIN_LIBRARY.is_file(),
            "plugin build did not produce {}".format(PLUGIN_LIBRARY),
        )

        sclang_result = run_checked(
            [
                sclang,
                "--include-path",
                str(ROOT / "plugin" / "ChaosOsc" / "Classes"),
                str(SCORE_SOURCE),
            ],
            environment,
        )
        self.assertIn(
            "CHAOSOSC_NRT_SCORE_WRITTEN",
            sclang_result.stdout + sclang_result.stderr,
        )
        self.assertTrue(OSC_SCORE.is_file(), "sclang did not write the NRT score")

        first_render = BUILD_DIR / "chaososc_nrt_first.wav"
        second_render = BUILD_DIR / "chaososc_nrt_second.wav"
        plugin_paths = [PLUGIN_BUILD_DIR] + discover_builtin_plugins(scsynth)
        plugin_path_argument = os.pathsep.join(str(path) for path in plugin_paths)
        for output_path in (first_render, second_render):
            server_result = run_checked(
                [
                    scsynth,
                    "-U",
                    plugin_path_argument,
                    "-o",
                    "3",
                    "-z",
                    str(BLOCK_SIZE),
                    "-D",
                    "0",
                    "-N",
                    str(OSC_SCORE),
                    "_",
                    str(output_path),
                    str(SAMPLE_RATE),
                    "WAV",
                    "float",
                ],
                environment,
            )
            self.assertTrue(
                output_path.is_file(),
                "scsynth did not write {}".format(output_path),
            )
            self.assertNotIn(
                "Unit generator 'ChaosOsc' not found",
                server_result.stdout + server_result.stderr,
            )

        first = read_float_wav(first_render)
        second = read_float_wav(second_render)
        for sample_rate, channels, bits, frames in (first, second):
            self.assertEqual(sample_rate, SAMPLE_RATE)
            self.assertEqual(channels, 3)
            self.assertEqual(bits, 32)
            self.assertAlmostEqual(
                len(frames) / sample_rate,
                DURATION_SECONDS,
                delta=max(0.005, 2 * BLOCK_SIZE / SAMPLE_RATE),
            )
            self.assertTrue(
                all(math.isfinite(sample) for frame in frames for sample in frame),
                "render contains non-finite samples",
            )
            self.assertTrue(
                all(channel_rms(frames, channel) > 0.005 for channel in range(3)),
                "render contains a silent or near-silent channel",
            )

        self.assertEqual(len(first[3]), len(second[3]))
        self.assertLessEqual(
            max(
                abs(left - right)
                for first_frame, second_frame in zip(first[3], second[3])
                for left, right in zip(first_frame, second_frame)
            ),
            1e-8,
            "fixed-seed NRT renders were not deterministic",
        )

        frames = first[3]
        change_frame = round(CONTROL_CHANGE_SECONDS * SAMPLE_RATE)
        self.assertLessEqual(
            max_channel_difference(frames, 0, 1),
            1e-7,
            "changing seed after Synth creation unexpectedly reseeded ChaosOsc",
        )
        self.assertLessEqual(
            max_channel_difference(frames, 0, 2, end=change_frame),
            1e-7,
            "control-rate chaosAmount differed before its scheduled update",
        )
        self.assertGreater(
            max_channel_difference(frames, 0, 2, start=change_frame),
            1e-4,
            "control-rate chaosAmount update did not affect the running UGen",
        )
        self.assertRegex(
            build_result.stdout,
            r"Verified exported plugin load symbol: _?load\b",
        )


if __name__ == "__main__":
    unittest.main()
