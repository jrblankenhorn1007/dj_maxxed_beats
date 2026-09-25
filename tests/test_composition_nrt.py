import math
import os
from pathlib import Path
import re
import shutil
import struct
import subprocess
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
CLASS_SOURCE = ROOT / "extension" / "Classes" / "MaxxedBeatsComposition.sc"
EXAMPLE_SOURCE = ROOT / "examples" / "procedural_chaos_garden.scd"
RENDERER = ROOT / "scripts" / "render_composition.py"
BUILD_DIR = ROOT / "tests" / ".build" / "composition-nrt"
PLUGIN_BUILD_SCRIPT = (
    ROOT / "plugin" / "ChaosOsc" / "Tests" / "build_plugin_smoke_test.sh"
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


def channel_rms(frames, channel):
    total = sum(frame[channel] * frame[channel] for frame in frames)
    return math.sqrt(total / len(frames))


class CompositionContractTests(unittest.TestCase):
    def test_renderer_refuses_to_overwrite_existing_wav_or_score(self):
        BUILD_DIR.mkdir(parents=True, exist_ok=True)
        output_path = BUILD_DIR / "overwrite-protection.wav"
        score_path = output_path.with_name(output_path.name + ".osc")
        original_wav = b"keep this existing WAV"
        original_score = b"keep this existing Score"
        output_path.write_bytes(original_wav)
        score_path.write_bytes(original_score)

        result = subprocess.run(
            [
                sys.executable,
                str(RENDERER),
                "--output",
                str(output_path),
                "--duration",
                "4.0",
                "--seed",
                "0.37",
            ],
            cwd=ROOT,
            env=os.environ.copy(),
            capture_output=True,
            text=True,
            timeout=120,
        )

        self.assertNotEqual(
            result.returncode,
            0,
            "the default render must not overwrite an existing WAV or Score",
        )
        self.assertIn("refusing to overwrite", result.stderr.lower())
        self.assertEqual(output_path.read_bytes(), original_wav)
        self.assertEqual(score_path.read_bytes(), original_score)

    def test_user_facing_composition_and_offline_render_workflow_exist(self):
        required_paths = (CLASS_SOURCE, EXAMPLE_SOURCE, RENDERER)
        missing = [
            str(path.relative_to(ROOT))
            for path in required_paths
            if not path.is_file()
        ]
        self.assertFalse(
            missing,
            "the user-facing ChaosOsc composition/NRT workflow is missing: "
            + ", ".join(missing),
        )

        class_source = CLASS_SOURCE.read_text(encoding="utf-8")
        example_source = EXAMPLE_SOURCE.read_text(encoding="utf-8")
        renderer_source = RENDERER.read_text(encoding="utf-8")
        example_code = re.sub(r"/\*.*?\*/", "", example_source, flags=re.DOTALL)
        self.assertIn("ChaosOsc.ar", class_source)
        self.assertIn("Score(", class_source)
        self.assertIn("MaxxedBeatsComposition.score", example_source)
        self.assertIn("writeOSCFile", example_source)
        self.assertIn('"WAV"', renderer_source)
        self.assertIn('"float"', renderer_source)
        self.assertIn('"-N"', renderer_source)
        self.assertIn('"2"', renderer_source)
        self.assertNotIn(".boot", renderer_source)
        self.assertNotIn(".play", example_code)


class CompositionNRTTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not RENDERER.is_file():
            raise unittest.SkipTest(
                "composition renderer is not implemented; see contract Red"
            )

        missing_runtime = [
            executable
            for environment_name, executable in (
                ("SCLANG", "sclang"),
                ("SCSYNTH", "scsynth"),
            )
            if not os.environ.get(environment_name) and not shutil.which(executable)
        ]
        if missing_runtime:
            raise unittest.SkipTest(
                "matching SuperCollider runtime unavailable: {}".format(
                    ", ".join(missing_runtime)
                )
            )
        cls.sclang = resolve_executable("SCLANG", "sclang")
        cls.scsynth = resolve_executable("SCSYNTH", "scsynth")

        BUILD_DIR.mkdir(parents=True, exist_ok=True)
        runtime_home = BUILD_DIR / "runtime-home"
        runtime_temp = BUILD_DIR / "runtime-tmp"
        runtime_home.mkdir(parents=True, exist_ok=True)
        runtime_temp.mkdir(parents=True, exist_ok=True)
        cls.environment = os.environ.copy()
        cls.environment.update(
            {
                "SCLANG": cls.sclang,
                "SCSYNTH": cls.scsynth,
                "HOME": str(runtime_home),
                "TMPDIR": str(runtime_temp),
                "XDG_CONFIG_HOME": str(runtime_home / ".config"),
                "XDG_DATA_HOME": str(runtime_home / ".local" / "share"),
            }
        )

        plugin_library = (
            ROOT / "plugin" / "ChaosOsc" / "Tests" / ".build" / "ChaosOsc.scx"
        )
        plugin_inputs = (
            PLUGIN_BUILD_SCRIPT,
            ROOT / "plugin" / "fetch_sc_plugin_api.py",
            ROOT / "plugin" / "ChaosOsc" / "Source" / "ChaosOsc.cpp",
            ROOT / "plugin" / "ChaosOsc" / "Source" / "ChaosOscCore.hpp",
        )
        build_required = not plugin_library.is_file() or any(
            path.stat().st_mtime_ns > plugin_library.stat().st_mtime_ns
            for path in plugin_inputs
        )
        cls.plugin_available = plugin_library.is_file() and not build_required
        if build_required:
            build_result = run_checked(
                ["bash", str(PLUGIN_BUILD_SCRIPT)],
                cls.environment,
                timeout=180,
            )
            cls.plugin_available = (
                "Verified exported plugin load symbol: _load"
                in build_result.stdout
            ) and plugin_library.is_file()

    def test_fixed_seed_stereo_nrt_render_is_valid_and_reproducible(self):
        self.assertTrue(
            getattr(self, "plugin_available", False),
            "ChaosOsc plugin is missing or its build did not verify the load symbol",
        )
        output_paths = [
            BUILD_DIR / "chaos_garden_seed_037.wav",
            BUILD_DIR / "chaos_garden_seed_037_repeat.wav",
            BUILD_DIR / "chaos_garden_seed_073.wav",
        ]
        for output_path, seed in zip(output_paths, ("0.37", "0.37", "0.73")):
            result = run_checked(
                [
                    sys.executable,
                    str(RENDERER),
                    "--output",
                    str(output_path),
                    "--duration",
                    "4.0",
                    "--seed",
                    seed,
                    "--overwrite",
                ],
                self.environment,
                timeout=120,
            )
            self.assertIn(
                "Wrote stereo float32 WAV",
                result.stdout + result.stderr,
            )
            self.assertTrue(output_path.is_file())

        renders = [read_float_wav(path) for path in output_paths]
        for sample_rate, channels, bits, frames in renders:
            self.assertEqual(sample_rate, 48000)
            self.assertEqual(channels, 2)
            self.assertEqual(bits, 32)
            self.assertAlmostEqual(
                len(frames) / sample_rate,
                4.0,
                delta=0.005,
            )
            self.assertTrue(
                all(math.isfinite(sample) for frame in frames for sample in frame),
                "render contains non-finite samples",
            )
            self.assertTrue(
                all(channel_rms(frames, channel) > 0.001 for channel in range(2)),
                "render contains a silent or near-silent channel",
            )

        first_frames = renders[0][3]
        repeated_frames = renders[1][3]
        other_seed_frames = renders[2][3]
        self.assertEqual(len(first_frames), len(repeated_frames))
        self.assertLessEqual(
            max(
                abs(first - repeated)
                for first_frame, repeated_frame in zip(
                    first_frames, repeated_frames
                )
                for first, repeated in zip(first_frame, repeated_frame)
            ),
            1e-8,
            "fixed-seed NRT renders were not deterministic",
        )
        self.assertEqual(len(first_frames), len(other_seed_frames))
        self.assertGreater(
            max(
                abs(first - other)
                for first_frame, other_frame in zip(first_frames, other_seed_frames)
                for first, other in zip(first_frame, other_frame)
            ),
            1e-4,
            "changing the composition seed did not change the render",
        )


if __name__ == "__main__":
    unittest.main()
