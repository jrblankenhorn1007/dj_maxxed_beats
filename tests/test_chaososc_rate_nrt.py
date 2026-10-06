"""Real sclang/scsynth NRT checks for ChaosOsc's iteration-rate API.

Renders tests/chaososc_rate_nrt_score.scd with the freshly built ChaosOsc
plugin and the repository's sclang class, then compares the rendered
channels with a double-precision reference model of ChaosOscCore. Proves in
scsynth that the default freq reproduces the original two-argument output
bit-exactly, that a low freq produces a smooth linearly interpolated signal,
that freq 0 holds, that ChaosOsc.kr runs, and that mul/add are applied.
"""

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
SCORE_SOURCE = TEST_DIR / "chaososc_rate_nrt_score.scd"
OSC_SCORE = BUILD_DIR / "chaososc_rate_nrt.osc"
RENDER_PATH = BUILD_DIR / "chaososc_rate_nrt.wav"
PLUGIN_BUILD_SCRIPT = (
    ROOT / "plugin" / "ChaosOsc" / "Tests" / "build_plugin_smoke_test.sh"
)
PLUGIN_BUILD_DIR = ROOT / "plugin" / "ChaosOsc" / "Tests" / ".build"
PLUGIN_LIBRARY = PLUGIN_BUILD_DIR / "ChaosOsc.scx"
SAMPLE_RATE = 48000
BLOCK_SIZE = 64
CONTROL_RATE = SAMPLE_RATE / BLOCK_SIZE
DURATION_SECONDS = 1.0
SYNTH_START_SECONDS = 0.01
HOLD_CHANGE_SECONDS = 0.5
SEED = 0.37
CHAOS_AMOUNT = 3.9
SLOW_FREQ = 100.0
CONTROL_SLOW_FREQ = 75.0
# Output channel order written by chaososc_rate_nrt_score.scd.
RATE_CHANNELS = (
    "two_arg",
    "explicit_default",
    "at_sample_rate",
    "legacy_two_input",
    "slow",
    "hold",
    "frozen",
    "control_default",
    "control_slow",
    "scaled",
)


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

    format_code, channels, sample_rate = struct.unpack_from("<HHI", format_chunk)
    bits_per_sample = struct.unpack_from("<H", format_chunk, 14)[0]
    if format_code == 0xFFFE and len(format_chunk) >= 40:
        format_code = struct.unpack_from("<I", format_chunk, 24)[0]
    if format_code != 3 or bits_per_sample != 32:
        raise AssertionError(
            "expected IEEE float32 WAV, got format {} with {} bits".format(
                format_code, bits_per_sample
            )
        )
    if channels < 1 or sample_rate < 1 or len(sample_chunk) % (4 * channels):
        raise AssertionError("WAV has invalid channel, rate, or sample data")

    samples = struct.unpack("<{}f".format(len(sample_chunk) // 4), sample_chunk)
    columns = [list(samples[channel::channels]) for channel in range(channels)]
    return sample_rate, channels, bits_per_sample, columns


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


def float32(value):
    return struct.unpack("<f", struct.pack("<f", value))[0]


class ReferenceChaosOsc:
    """Double-precision mirror of chaososc::ChaosOscCore for one UGen."""

    def __init__(self, seed, freq, sample_rate):
        self.previous = seed
        self.state = seed
        self.phase = 1.0
        if freq >= sample_rate:
            self.increment = 1.0
        elif freq <= 0.0:
            self.increment = 0.0
        else:
            self.increment = freq / sample_rate

    def _advance(self, chaos_amount):
        self.previous = self.state
        self.state = chaos_amount * self.state * (1.0 - self.state)

    def next(self, chaos_amount):
        if self.increment >= 1.0:
            self._advance(chaos_amount)
            self.phase = 1.0
        elif self.increment > 0.0:
            self.phase += self.increment
            if self.phase > 1.0:
                self.phase -= 1.0
                self._advance(chaos_amount)
        if self.phase >= 1.0:
            value = self.state
        else:
            value = self.previous + (self.state - self.previous) * self.phase
        return float32(value * 2.0 - 1.0)


def reference_render(freq, sample_rate, count):
    """Expected output of ChaosOsc(CHAOS_AMOUNT, SEED, freq) from its first
    calculated block. The Ctor's initialisation sample runs the calc function
    once, so the core has already advanced once when the first block runs."""
    core = ReferenceChaosOsc(float32(SEED), float32(freq), sample_rate)
    chaos_amount = float32(CHAOS_AMOUNT)
    initialisation_sample = core.next(chaos_amount)
    return initialisation_sample, [core.next(chaos_amount) for _ in range(count)]


def max_step(samples):
    return max(abs(right - left) for left, right in zip(samples, samples[1:]))


class ChaosOscRateNRTIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
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

        run_checked(["bash", str(PLUGIN_BUILD_SCRIPT)], environment, timeout=180)
        if not PLUGIN_LIBRARY.is_file():
            raise AssertionError(
                "plugin build did not produce {}".format(PLUGIN_LIBRARY)
            )

        if OSC_SCORE.exists():
            OSC_SCORE.unlink()
        sclang_result = run_checked(
            [
                sclang,
                "--include-path",
                str(ROOT / "plugin" / "ChaosOsc" / "Classes"),
                str(SCORE_SOURCE),
            ],
            environment,
        )
        cls.sclang_output = sclang_result.stdout + sclang_result.stderr
        if "CHAOSOSC_RATE_NRT_SCORE_WRITTEN" not in cls.sclang_output:
            raise AssertionError(
                "sclang did not write the rate score:\n" + cls.sclang_output
            )

        if RENDER_PATH.exists():
            RENDER_PATH.unlink()
        plugin_paths = [PLUGIN_BUILD_DIR] + discover_builtin_plugins(scsynth)
        server_result = run_checked(
            [
                scsynth,
                "-U",
                os.pathsep.join(str(path) for path in plugin_paths),
                "-o",
                str(len(RATE_CHANNELS)),
                "-z",
                str(BLOCK_SIZE),
                "-D",
                "0",
                "-N",
                str(OSC_SCORE),
                "_",
                str(RENDER_PATH),
                str(SAMPLE_RATE),
                "WAV",
                "float",
            ],
            environment,
        )
        cls.server_output = server_result.stdout + server_result.stderr
        (
            cls.sample_rate,
            cls.channel_count,
            cls.bits,
            columns,
        ) = read_float_wav(RENDER_PATH)
        cls.channels = dict(zip(RATE_CHANNELS, columns))
        cls.frame_count = len(columns[0])
        cls.onset = next(
            (
                index
                for index in range(cls.frame_count)
                if any(column[index] != 0.0 for column in columns)
            ),
            None,
        )

    def active(self, name):
        return self.channels[name][self.onset :]

    def test_sclang_class_defaults_rates_and_madd(self):
        for expected in (
            "CHAOSOSC_AR_DEFAULT: ChaosOsc audio [3.9, 0.5, inf]",
            "CHAOSOSC_KR_DEFAULT: ChaosOsc control [3.9, 0.5, inf]",
            "CHAOSOSC_UNITY_MADD: ChaosOsc",
            "CHAOSOSC_SCALED_MADD: MulAdd [0.25, 0.5]",
        ):
            with self.subTest(expected=expected):
                self.assertIn(expected, self.sclang_output)

    def test_render_is_a_valid_finite_float_wav(self):
        self.assertNotIn("Unit generator 'ChaosOsc' not found", self.server_output)
        self.assertEqual(self.sample_rate, SAMPLE_RATE)
        self.assertEqual(self.channel_count, len(RATE_CHANNELS))
        self.assertEqual(self.bits, 32)
        self.assertAlmostEqual(
            self.frame_count / SAMPLE_RATE,
            DURATION_SECONDS,
            delta=max(0.005, 2 * BLOCK_SIZE / SAMPLE_RATE),
        )
        self.assertIsNotNone(self.onset, "render is silent")
        self.assertLessEqual(
            self.onset, round(SYNTH_START_SECONDS * SAMPLE_RATE) + BLOCK_SIZE
        )
        for name, column in self.channels.items():
            with self.subTest(channel=name):
                self.assertTrue(all(math.isfinite(sample) for sample in column))
                self.assertTrue(all(sample == 0.0 for sample in column[: self.onset]))

    def test_default_freq_reproduces_the_original_output_bit_exactly(self):
        two_arg = self.active("two_arg")
        _, expected = reference_render(math.inf, SAMPLE_RATE, len(two_arg))
        self.assertEqual(
            two_arg,
            expected,
            "2-arg ChaosOsc.ar no longer matches the original one-step-per-"
            "sample logistic output",
        )
        for name in ("explicit_default", "at_sample_rate", "legacy_two_input"):
            with self.subTest(channel=name):
                self.assertEqual(self.channels[name], self.channels["two_arg"])

    def test_low_freq_is_a_smooth_linear_interpolation_of_the_map(self):
        slow = self.active("slow")
        _, expected = reference_render(SLOW_FREQ, SAMPLE_RATE, len(slow))
        self.assertLessEqual(
            max(abs(actual - wanted) for actual, wanted in zip(slow, expected)),
            1e-6,
            "low-freq output is not the linear interpolation of the map",
        )
        self.assertLessEqual(max_step(slow), 2.0 * SLOW_FREQ / SAMPLE_RATE + 1e-6)
        self.assertGreater(max(slow) - min(slow), 0.5, "low-freq output is flat")
        self.assertGreater(max_step(self.active("two_arg")), 0.5)
        self.assertGreater(
            max(
                abs(left - right)
                for left, right in zip(slow, self.active("two_arg"))
            ),
            0.1,
            "low freq did not change the output",
        )

    def test_zero_freq_holds_the_current_value(self):
        frozen = self.active("frozen")
        self.assertEqual(
            set(frozen), {float32(float32(SEED) * 2.0 - 1.0)}, "freq 0 did not hold"
        )

        hold = self.channels["hold"]
        slow = self.channels["slow"]
        change_frame = round(HOLD_CHANGE_SECONDS * SAMPLE_RATE)
        first_difference = next(
            index for index in range(self.frame_count) if hold[index] != slow[index]
        )
        self.assertGreaterEqual(first_difference, change_frame - BLOCK_SIZE)
        self.assertLessEqual(first_difference, change_frame + BLOCK_SIZE)
        held_value = hold[first_difference - 1]
        self.assertEqual(
            set(hold[first_difference:]),
            {held_value},
            "setting freq to 0 did not freeze the running oscillator",
        )
        self.assertGreater(
            len(set(hold[self.onset : first_difference])),
            100,
            "the oscillator was not moving before freq was set to 0",
        )

    def test_control_rate_constructor_runs_at_control_rate(self):
        control = self.active("control_default")
        block_starts = control[::BLOCK_SIZE]
        self.assertTrue(all(-1.0 <= sample <= 1.0 for sample in control))
        self.assertGreater(len(set(block_starts)), 100, ".kr output is constant")
        initialisation_sample, expected = reference_render(
            math.inf, CONTROL_RATE, len(block_starts)
        )
        # K2A ramps from the previous control value, so each block starts at
        # the value ChaosOsc.kr produced for the preceding block.
        self.assertEqual(
            block_starts, ([initialisation_sample] + expected)[: len(block_starts)]
        )

        control_slow = self.active("control_slow")
        slow_block_starts = control_slow[::BLOCK_SIZE]
        self.assertGreater(len(set(control_slow)), 100, "slow .kr output is constant")
        self.assertLessEqual(
            max_step(control_slow),
            2.0 * CONTROL_SLOW_FREQ / CONTROL_RATE / BLOCK_SIZE + 1e-6,
        )
        # The interpolation step is freq / controlRate for .kr units.
        initialisation_sample, expected = reference_render(
            CONTROL_SLOW_FREQ, CONTROL_RATE, len(slow_block_starts)
        )
        self.assertLessEqual(
            max(
                abs(actual - wanted)
                for actual, wanted in zip(
                    slow_block_starts, [initialisation_sample] + expected
                )
            ),
            1e-6,
            "slow .kr output does not interpolate at the control rate",
        )

    def test_mul_and_add_scale_the_output(self):
        scaled = self.active("scaled")
        two_arg = self.active("two_arg")
        self.assertLessEqual(
            max(
                abs(actual - (source * 0.25 + 0.5))
                for actual, source in zip(scaled, two_arg)
            ),
            1e-6,
        )
        self.assertGreater(min(scaled), 0.0)


if __name__ == "__main__":
    unittest.main()
