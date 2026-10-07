"""Opt-in real-time audition of the ChaosOsc UGen in a CoreAudio scsynth.

CI runners have no audio device, so the audition is skipped unless
DJMB_REALTIME_AUDIO_TESTS=1. Once enabled it never skips: a missing
sclang/scsynth, plugin build failure, or failed server boot fails the test.

tests/chaososc_realtime.scd boots a real-time scsynth through sclang on a free
127.0.0.1 UDP port with no input channels, using the CoreAudio default output
device at its current sample rate. ChaosOsc renders only to private audio
buses, which RecordBuf captures together with the hardware output buses; the
test requires the hardware outputs to be exact zeros, so nothing reaches the
speakers.

Microphone safety: without -H, SuperCollider 3.14.1's CoreAudio driver always
starts the default *input* device when it differs from the output device (as
on MacBook built-in microphone/speakers), even with zero input channels,
which makes macOS gate the boot on a microphone-permission prompt. The
audition therefore names the default output device for both directions
(ServerOptions.device) and refuses devices that have input channels.
DJMB_REALTIME_AUDIO_DEVICE may name a different output-only device.

Run it locally with, for example:

    DJMB_REALTIME_AUDIO_TESTS=1 SCLANG=/path/to/sclang SCSYNTH=/path/to/scsynth \
        PYTHONDONTWRITEBYTECODE=1 python3 -m unittest -v tests/test_chaososc_realtime.py
"""

import json
import math
import os
from pathlib import Path
import re
import shutil
import signal
import socket
import struct
import subprocess
import sys
import time
import unittest


ROOT = Path(__file__).resolve().parents[1]
TEST_DIR = ROOT / "tests"
BUILD_DIR = TEST_DIR / ".build"
OUTPUT_DIR = BUILD_DIR / "chaososc-realtime"
CAPTURE_PATH = OUTPUT_DIR / "chaososc_realtime_capture.wav"
SUMMARY_PATH = OUTPUT_DIR / "summary.json"
SCLANG_LOG_PATH = OUTPUT_DIR / "sclang_output.log"
AUDITION_SCRIPT = TEST_DIR / "chaososc_realtime.scd"
PLUGIN_DIR = ROOT / "plugin" / "ChaosOsc"
PLUGIN_CLASSES_DIR = PLUGIN_DIR / "Classes"
PLUGIN_BUILD_SCRIPT = PLUGIN_DIR / "Tests" / "build_plugin_smoke_test.sh"
PLUGIN_BUILD_DIR = PLUGIN_DIR / "Tests" / ".build"
PLUGIN_LIBRARY = PLUGIN_BUILD_DIR / "ChaosOsc.scx"
PLUGIN_BUILD_INPUTS = (
    PLUGIN_BUILD_SCRIPT,
    ROOT / "plugin" / "fetch_sc_plugin_api.py",
    PLUGIN_DIR / "Source",
)

OPT_IN_VARIABLE = "DJMB_REALTIME_AUDIO_TESTS"
DEVICE_VARIABLE = "DJMB_REALTIME_AUDIO_DEVICE"
SKIP_REASON = (
    "real-time audio test is opt-in: set {}=1 on a machine with an audio "
    "output device (CI runners have none)".format(OPT_IN_VARIABLE)
)
SERVER_NAME = "djmbChaosOscRealtime"
CAPTURE_SECONDS = 2.0
TWIN_SET_SECONDS = 1.0
TWIN_SET_TOLERANCE_SECONDS = 0.05
WORKLOAD_SYNTHS = 64
# reference ChaosOsc.ar(3.9, 0.37), its .set twin, the workload mix, and the
# two hardware output buses.
CAPTURE_CHANNELS = 5
HARDWARE_OUTPUT_CHANNELS = (3, 4)
PEAK_CPU_LIMIT_PERCENT = 50.0
BOOT_TIMEOUT_SECONDS = 30
WATCHDOG_SECONDS = 75
SCLANG_TIMEOUT_SECONDS = 120
PLUGIN_BUILD_TIMEOUT_SECONDS = 300
# scsynth/sclang default ports; never hand these to the audition server.
RESERVED_PORTS = range(57110, 57131)

FORBIDDEN_OUTPUT_PATTERNS = (
    re.compile(r"FAILURE IN SERVER"),
    re.compile(r"not found", re.IGNORECASE),
    re.compile(r"not installed", re.IGNORECASE),
    re.compile(r"\blate\b", re.IGNORECASE),
    re.compile(r"\bERROR\b"),
    re.compile(r"\bexception\b", re.IGNORECASE),
    re.compile(r"^DJMB_RT FAIL\b"),
)


def realtime_tests_enabled():
    return os.environ.get(OPT_IN_VARIABLE, "").strip() == "1"


def resolve_executable(environment_name, executable_name):
    hint = (
        "{} enabled the real-time ChaosOsc audition, which needs the "
        "SuperCollider {} executable: set {} to its path (for "
        "SuperCollider.app use Contents/MacOS/sclang and "
        "Contents/Resources/scsynth) or put {} on PATH"
    ).format(OPT_IN_VARIABLE, executable_name, environment_name, executable_name)
    configured = os.environ.get(environment_name)
    if configured:
        candidate = Path(configured)
        if not candidate.is_absolute():
            candidate = ROOT / candidate
        if candidate.is_file() and os.access(str(candidate), os.X_OK):
            return str(candidate.resolve())
        resolved = shutil.which(configured)
        if resolved:
            return resolved
        raise AssertionError(
            "{}={} is not an executable file. {}".format(
                environment_name, configured, hint
            )
        )

    resolved = shutil.which(executable_name)
    if resolved:
        return resolved
    raise AssertionError("{} was not found. {}".format(executable_name, hint))


def isolated_environment():
    environment = os.environ.copy()
    runtime_home = BUILD_DIR / "realtime-home"
    runtime_temp = BUILD_DIR / "realtime-tmp"
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
    return environment


def plugin_library_is_stale():
    if not PLUGIN_LIBRARY.is_file():
        return True
    built_at = PLUGIN_LIBRARY.stat().st_mtime
    for source in PLUGIN_BUILD_INPUTS:
        if source.is_dir():
            paths = [path for path in source.rglob("*") if path.is_file()]
        else:
            paths = [source]
        if any(path.stat().st_mtime > built_at for path in paths):
            return True
    return False


def run_checked(command, environment, timeout):
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
            "command failed ({}): {}\n{}\n{}".format(
                result.returncode, " ".join(command), result.stdout, result.stderr
            )
        )
    return result


def discover_builtin_plugin_dirs(scsynth):
    configured = os.environ.get("SC_DEFAULT_PLUGIN_PATH")
    if configured:
        candidates = [
            Path(path) if Path(path).is_absolute() else ROOT / path
            for path in configured.split(os.pathsep)
            if path
        ]
        missing = [str(path) for path in candidates if not path.is_dir()]
        if missing:
            raise AssertionError(
                "SC_DEFAULT_PLUGIN_PATH entries do not exist: {}".format(
                    ", ".join(missing)
                )
            )
    else:
        executable = Path(scsynth).resolve()
        candidates = [
            directory / name
            for directory in (executable.parent, executable.parent.parent / "Resources")
            for name in ("plugins", "Plugins")
        ]

    unique_dirs = []
    seen = set()
    for path in candidates:
        if not path.is_dir():
            continue
        # macOS volumes are usually case-insensitive, so plugins/ and Plugins/
        # can be one directory; scsynth must not load the same plugins twice.
        status = path.stat()
        identity = (status.st_dev, status.st_ino)
        if identity not in seen:
            unique_dirs.append(path.resolve())
            seen.add(identity)
    if not unique_dirs:
        raise AssertionError(
            "no built-in UGen plugin directory found next to {}; set "
            "SC_DEFAULT_PLUGIN_PATH to the SuperCollider plugins directory".format(
                scsynth
            )
        )
    return unique_dirs


def validate_device_name(name):
    """Reject device names that SuperCollider would pass unescaped to a shell.

    Server:boot quotes the -H device name without escaping it before running
    the command through /bin/sh, so backquotes, $, double quotes, backslashes,
    or control characters in a device name could run commands.
    """
    unsafe = [
        character
        for character in name
        if character in '`$"\\' or ord(character) < 32 or ord(character) == 127
    ]
    if unsafe:
        raise AssertionError(
            "refusing audio device name {!r}: it contains characters ({}) that "
            "SuperCollider passes unescaped to a shell; rename the device or set "
            "{} to another output-only device".format(
                name, ", ".join(sorted(set(repr(c) for c in unsafe))),
                DEVICE_VARIABLE,
            )
        )
    return name


def select_output_only_device():
    """Name the CoreAudio output device to pin for both scsynth directions."""
    system_profiler = shutil.which("system_profiler")
    if system_profiler is None:
        raise AssertionError(
            "the real-time ChaosOsc audition supports macOS CoreAudio only "
            "(system_profiler is unavailable)"
        )
    result = run_checked(
        [system_profiler, "SPAudioDataType", "-json"], os.environ.copy(), timeout=60
    )
    devices = [
        item
        for group in json.loads(result.stdout).get("SPAudioDataType", [])
        for item in group.get("_items", [])
    ]
    requested = os.environ.get(DEVICE_VARIABLE, "").strip()
    if requested:
        matches = [device for device in devices if device.get("_name") == requested]
    else:
        matches = [
            device
            for device in devices
            if device.get("coreaudio_default_audio_output_device") == "spaudio_yes"
        ]
    if len(matches) != 1 or not matches[0].get("coreaudio_device_output"):
        raise AssertionError(
            "could not resolve {} to one CoreAudio output device; "
            "system_profiler lists: {}".format(
                "{}={}".format(DEVICE_VARIABLE, requested)
                if requested
                else "the default output device",
                ", ".join(str(device.get("_name")) for device in devices),
            )
        )
    device = matches[0]
    if device.get("coreaudio_device_input"):
        raise AssertionError(
            "audio device {!r} also has input channels, so starting it would "
            "need microphone access; set {} to an output-only device".format(
                device["_name"], DEVICE_VARIABLE
            )
        )
    return validate_device_name(device["_name"])


def find_free_udp_port():
    for _attempt in range(20):
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
            probe.bind(("127.0.0.1", 0))
            port = probe.getsockname()[1]
        if port not in RESERVED_PORTS:
            return port
    raise AssertionError("could not find a free UDP port on 127.0.0.1")


def list_processes():
    result = subprocess.run(
        ["ps", "-axww", "-o", "pid=,pgid=,command="],
        capture_output=True,
        text=True,
        timeout=10,
    )
    processes = []
    for line in result.stdout.splitlines():
        fields = line.split(None, 2)
        if len(fields) != 3:
            continue
        try:
            pid, process_group = int(fields[0]), int(fields[1])
        except ValueError:
            continue
        processes.append((pid, process_group, fields[2]))
    return processes


def find_audition_processes(port, process_group=None):
    # argv[0] must be scsynth itself, not a shell command that mentions it.
    server_pattern = re.compile(
        r"^(?:\S*/)?scsynth\s(?:.*\s)?-u\s+{}(?:\s|$)".format(port)
    )
    return [
        (pid, command)
        for pid, group, command in list_processes()
        if pid != os.getpid()
        and (
            server_pattern.search(command)
            or (process_group is not None and group == process_group)
        )
    ]


def kill_audition_processes(port, process_group=None, grace_seconds=0.0):
    """Return audition processes still alive after the grace period, killed."""
    deadline = time.monotonic() + grace_seconds
    leftovers = find_audition_processes(port, process_group)
    while leftovers and time.monotonic() < deadline:
        time.sleep(0.1)
        leftovers = find_audition_processes(port, process_group)
    for pid, _command in leftovers:
        try:
            os.kill(pid, signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            pass
    return leftovers


def run_audition(command, environment, timeout, port):
    process = subprocess.Popen(
        command,
        cwd=ROOT,
        env=environment,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        start_new_session=True,
    )
    try:
        output, _ = process.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            process.kill()
        # scsynth may hold the inherited output pipe open from another group
        kill_audition_processes(port, process.pid)
        try:
            output, _ = process.communicate(timeout=10)
        except subprocess.TimeoutExpired:
            output = "(output unavailable: the pipe stayed open)"
        raise AssertionError(
            "sclang real-time audition timed out after {} s and was killed; "
            "output:\n{}".format(timeout, output)
        )
    finally:
        if process.poll() is None:
            process.kill()
            process.wait()
        process.stdout.close()
    return process.pid, process.returncode, output


def parse_report(output):
    """Collect the audition's 'DJMB_RT <EVENT> key=value ...' lines."""
    events = {}
    for line in output.splitlines():
        if not line.startswith("DJMB_RT "):
            continue
        parts = line.split()
        if len(parts) < 2:
            continue
        fields = dict(part.split("=", 1) for part in parts[2:] if "=" in part)
        events.setdefault(parts[1], []).append(fields)
    return events


def find_forbidden_output(output):
    return [
        line
        for line in output.splitlines()
        if any(pattern.search(line) for pattern in FORBIDDEN_OUTPUT_PATTERNS)
    ]


def describe_audio_device(output):
    devices = re.findall(r'^"([^"\n]+)" Output Device$', output, re.MULTILINE)
    driver = re.search(
        r"SC_AudioDriver: sample rate = ([0-9.]+), driver's block size = (\d+)",
        output,
    )
    return {
        "outputDevice": devices[-1] if devices else None,
        "driverSampleRate": float(driver.group(1)) if driver else None,
        "driverBlockSize": int(driver.group(2)) if driver else None,
    }


def read_float_wav(path):
    data = path.read_bytes()
    if len(data) < 12 or data[:4] != b"RIFF" or data[8:12] != b"WAVE":
        raise AssertionError("{} is not a RIFF/WAVE file".format(path))

    format_chunk = None
    sample_chunk = None
    offset = 12
    while offset + 8 <= len(data):
        chunk_name, chunk_size = struct.unpack_from("<4sI", data, offset)
        chunk_start = offset + 8
        chunk_end = chunk_start + chunk_size
        if chunk_end > len(data):
            raise AssertionError("WAV chunk extends beyond the file")
        if chunk_name == b"fmt ":
            format_chunk = data[chunk_start:chunk_end]
        elif chunk_name == b"data":
            sample_chunk = data[chunk_start:chunk_end]
        offset = chunk_end + (chunk_size & 1)

    if format_chunk is None or sample_chunk is None or len(format_chunk) < 16:
        raise AssertionError("WAV is missing its format or audio-data chunk")
    format_code, channels, sample_rate, _rate, _align, bits = struct.unpack_from(
        "<HHIIHH", format_chunk
    )
    if format_code == 0xFFFE and len(format_chunk) >= 40:
        format_code = struct.unpack_from("<I", format_chunk, 24)[0]
    if format_code != 3 or bits != 32:
        raise AssertionError(
            "expected an IEEE float32 WAV, got format {} with {} bits".format(
                format_code, bits
            )
        )
    if channels < 1 or len(sample_chunk) % (4 * channels):
        raise AssertionError("WAV sample data is not aligned to its channels")
    samples = struct.unpack("<{}f".format(len(sample_chunk) // 4), sample_chunk)
    return sample_rate, [samples[channel::channels] for channel in range(channels)]


def rms(samples):
    return math.sqrt(sum(sample * sample for sample in samples) / len(samples))


def to_float32(value):
    return struct.unpack("<f", struct.pack("<f", value))[0]


def logistic_model_offset(samples, chaos_amount, seed, max_offset=4):
    """Offset at which samples equal the documented logistic-map DSP, or None.

    Informational only: it documents bit-exactness without making this
    audition depend on DSP details beyond ChaosOsc.ar(chaosAmount, seed).
    """
    growth_rate = to_float32(chaos_amount)
    state = to_float32(seed)
    model = []
    for _index in range(len(samples) + max_offset):
        state = growth_rate * state * (1.0 - state)
        model.append(to_float32(state * 2.0 - 1.0))
    for offset in range(max_offset + 1):
        if all(model[offset + index] == sample for index, sample in enumerate(samples)):
            return offset
    return None


class ChaosOscRealtimeAuditionTests(unittest.TestCase):
    def setUp(self):
        if not realtime_tests_enabled():
            raise unittest.SkipTest(SKIP_REASON)

    def test_realtime_server_renders_chaososc_silently_under_live_workload(self):
        audition = self.run_realtime_audition()
        summary = {"port": audition["port"], "workloadSynths": WORKLOAD_SYNTHS}
        summary.update(self.check_realtime_boot(audition))
        summary.update(self.check_server_health(audition))
        summary.update(self.check_capture(audition, summary["sampleRate"]))
        SUMMARY_PATH.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
        sys.stderr.write(
            "\nChaosOsc real-time audition: {}\n".format(
                json.dumps(summary, sort_keys=True)
            )
        )

    def run_realtime_audition(self):
        sclang = resolve_executable("SCLANG", "sclang")
        scsynth = resolve_executable("SCSYNTH", "scsynth")
        self.assertTrue(
            AUDITION_SCRIPT.is_file(),
            "missing real-time audition script {}".format(AUDITION_SCRIPT),
        )
        environment = isolated_environment()
        if plugin_library_is_stale():
            run_checked(
                ["bash", str(PLUGIN_BUILD_SCRIPT)],
                environment,
                timeout=PLUGIN_BUILD_TIMEOUT_SECONDS,
            )
        self.assertFalse(
            plugin_library_is_stale(),
            "plugin build did not produce an up-to-date {}".format(PLUGIN_LIBRARY),
        )
        plugin_dirs = [PLUGIN_BUILD_DIR.resolve()] + discover_builtin_plugin_dirs(
            scsynth
        )
        audio_device = select_output_only_device()
        port = find_free_udp_port()
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        for stale_output in (CAPTURE_PATH, SUMMARY_PATH, SCLANG_LOG_PATH):
            if stale_output.exists():
                stale_output.unlink()
        environment.update(
            {
                "DJMB_RT_PORT": str(port),
                "DJMB_RT_DEVICE": audio_device,
                "DJMB_RT_SCSYNTH": scsynth,
                "DJMB_RT_PLUGIN_PATHS": os.pathsep.join(map(str, plugin_dirs)),
                "DJMB_RT_CAPTURE_PATH": str(CAPTURE_PATH),
                "DJMB_RT_CAPTURE_SECONDS": str(CAPTURE_SECONDS),
                "DJMB_RT_TWIN_SET_SECONDS": str(TWIN_SET_SECONDS),
                "DJMB_RT_WORKLOAD_SYNTHS": str(WORKLOAD_SYNTHS),
                "DJMB_RT_BOOT_TIMEOUT_SECONDS": str(BOOT_TIMEOUT_SECONDS),
                "DJMB_RT_WATCHDOG_SECONDS": str(WATCHDOG_SECONDS),
            }
        )
        # Safety net for every failure path; the leftover check below makes a
        # server that outlives a clean sclang exit fail the test.
        self.addCleanup(kill_audition_processes, port)
        sclang_pid, returncode, output = run_audition(
            [sclang, "--include-path", str(PLUGIN_CLASSES_DIR), str(AUDITION_SCRIPT)],
            environment,
            SCLANG_TIMEOUT_SECONDS,
            port,
        )
        self.addCleanup(kill_audition_processes, port, sclang_pid)
        SCLANG_LOG_PATH.write_text(output)
        diagnostics = "sclang real-time audition output ({}):\n{}".format(
            SCLANG_LOG_PATH, output
        )
        leftovers = kill_audition_processes(port, sclang_pid, grace_seconds=3.0)
        self.assertEqual(
            leftovers, [], "processes outlived sclang and were killed\n" + diagnostics
        )
        self.assertEqual(returncode, 0, diagnostics)
        self.assertEqual(find_forbidden_output(output), [], diagnostics)
        events = parse_report(output)
        for event in ("BOOTED", "CPU_SAMPLE", "STATUS", "CAPTURE", "CPU", "QUIT", "DONE"):
            self.assertIn(event, events, diagnostics)
        return {
            "device": audio_device,
            "port": port,
            "output": output,
            "events": events,
            "diagnostics": diagnostics,
        }

    def check_realtime_boot(self, audition):
        output, diagnostics = audition["output"], audition["diagnostics"]
        driver = describe_audio_device(output)
        self.assertIsNotNone(
            driver["driverSampleRate"],
            "scsynth did not report starting its real-time audio driver\n"
            + diagnostics,
        )
        self.assertEqual(driver["outputDevice"], audition["device"], diagnostics)
        # With one device named for both directions, scsynth reports that
        # output-only device (0 input streams) as its input device: no microphone.
        self.assertEqual(
            set(re.findall(r'^"([^"\n]+)" Input Device$', output, re.MULTILINE)),
            {audition["device"]},
            diagnostics,
        )
        booted = audition["events"]["BOOTED"][0]
        self.assertEqual(booted["serverRunning"], "true", diagnostics)
        self.assertEqual(int(booted["port"]), audition["port"], diagnostics)
        sample_rate = float(booted["sampleRate"])
        actual_sample_rate = float(booted["actualSampleRate"])
        self.assertGreater(sample_rate, 0, diagnostics)
        self.assertAlmostEqual(
            actual_sample_rate, sample_rate, delta=0.01 * sample_rate, msg=diagnostics
        )
        self.assertAlmostEqual(
            driver["driverSampleRate"], sample_rate, delta=0.5, msg=diagnostics
        )
        return dict(
            driver, sampleRate=sample_rate, actualSampleRate=actual_sample_rate
        )

    def check_server_health(self, audition):
        events, diagnostics = audition["events"], audition["diagnostics"]
        statuses = {fields["phase"]: fields for fields in events["STATUS"]}
        for phase, expected_synths in (
            ("workload", WORKLOAD_SYNTHS + 2),
            ("workloadFreed", 2),
            ("allFreed", 0),
        ):
            with self.subTest(phase=phase):
                self.assertIn(phase, statuses, diagnostics)
                status = statuses[phase]
                self.assertEqual(status["serverRunning"], "true", diagnostics)
                self.assertEqual(int(status["numSynths"]), expected_synths, diagnostics)
                self.assertLess(
                    float(status["peakCPU"]), PEAK_CPU_LIMIT_PERCENT, diagnostics
                )
        self.assertGreaterEqual(
            int(statuses["workload"]["numUGens"]), 2 * (WORKLOAD_SYNTHS + 2)
        )

        cpu = events["CPU"][0]
        live_max_peak_cpu = float(cpu["liveMaxPeakCPU"])
        self.assertTrue(math.isfinite(live_max_peak_cpu), diagnostics)
        self.assertGreaterEqual(live_max_peak_cpu, 0.0, diagnostics)
        self.assertLess(live_max_peak_cpu, PEAK_CPU_LIMIT_PERCENT, diagnostics)
        self.assertEqual(int(cpu["serverFailures"]), 0, diagnostics)
        self.assertGreaterEqual(int(cpu["liveReplies"]), 5, diagnostics)
        # reference + twin + recorder + workload ran together in the live window
        self.assertIn(
            WORKLOAD_SYNTHS + 3,
            {
                int(sample["numSynths"])
                for sample in events["CPU_SAMPLE"]
                if sample["window"] == "live"
            },
            diagnostics,
        )

        quit_report = events["QUIT"][0]
        self.assertEqual(quit_report["quitAcknowledged"], "true", diagnostics)
        self.assertEqual(quit_report["serverProcessExited"], "true", diagnostics)
        self.assertRegex(
            audition["output"],
            r"Server '{}' exited with exit code 0\.".format(SERVER_NAME),
        )
        return {
            "statusReplies": int(cpu["statusReplies"]),
            "liveStatusReplies": int(cpu["liveReplies"]),
            "liveMaxAvgCPU": float(cpu["liveMaxAvgCPU"]),
            "liveMaxPeakCPU": live_max_peak_cpu,
            "bootMaxPeakCPU": float(cpu["bootMaxPeakCPU"]),
            "warmupMaxPeakCPU": float(cpu["warmupMaxPeakCPU"]),
            "finalAvgCPU": float(cpu["avgCPU"]),
            "finalPeakCPU": float(cpu["peakCPU"]),
            "workloadPeakCPU": float(statuses["workload"]["peakCPU"]),
            "workloadNumUGens": int(statuses["workload"]["numUGens"]),
            "maxNumSynths": int(cpu["maxNumSynths"]),
        }

    def check_capture(self, audition, sample_rate):
        capture = audition["events"]["CAPTURE"][0]
        self.assertEqual(float(capture["twinSetSeconds"]), TWIN_SET_SECONDS)
        capture_wall_seconds = float(capture["captureWallSeconds"])
        # paced by the audio clock: no faster than real time
        self.assertGreaterEqual(capture_wall_seconds, 0.95 * CAPTURE_SECONDS)
        self.assertLessEqual(capture_wall_seconds, CAPTURE_SECONDS + 3.0)
        self.assertTrue(CAPTURE_PATH.is_file(), "capture WAV was not written")
        wav_rate, channels = read_float_wav(CAPTURE_PATH)
        self.assertEqual(wav_rate, round(sample_rate))
        self.assertEqual(len(channels), CAPTURE_CHANNELS)
        frames = len(channels[0])
        self.assertEqual(frames, int(capture["frames"]))
        self.assertAlmostEqual(frames / wav_rate, CAPTURE_SECONDS, delta=2.0 / wav_rate)

        reference, twin, workload = channels[0], channels[1], channels[2]
        for name, samples, minimum_rms in (
            ("reference", reference, 0.1),
            ("twin", twin, 0.1),
            ("workload", workload, 0.01),
        ):
            with self.subTest(channel=name):
                self.assertTrue(all(math.isfinite(sample) for sample in samples))
                self.assertLessEqual(max(abs(sample) for sample in samples), 1.0)
                self.assertGreater(rms(samples), minimum_rms)
                # recorded right up to the end of the buffer
                self.assertGreater(rms(samples[-int(0.01 * wav_rate) :]), minimum_rms)
        self.assertGreater(len(set(reference)), 1000, "reference is not chaotic")
        for channel in HARDWARE_OUTPUT_CHANNELS:
            self.assertTrue(
                all(sample == 0.0 for sample in channels[channel]),
                "hardware output bus {} was not silent".format(channel - 3),
            )

        # The twin matches the reference sample for sample until its live
        # chaosAmount .set, scheduled TWIN_SET_SECONDS after the shared start.
        divergence = next(
            (index for index, pair in enumerate(zip(reference, twin)) if pair[0] != pair[1]),
            None,
        )
        self.assertIsNotNone(divergence, "live chaosAmount .set had no effect")
        self.assertAlmostEqual(
            divergence / wav_rate,
            TWIN_SET_SECONDS,
            delta=TWIN_SET_TOLERANCE_SECONDS,
            msg="twin diverged from the reference away from its scheduled .set",
        )
        after_set = range(divergence, frames)
        self.assertGreater(
            sum(abs(reference[index] - twin[index]) for index in after_set)
            / len(after_set),
            0.05,
        )
        return {
            "captureFrames": frames,
            "captureWallSeconds": capture_wall_seconds,
            "twinDivergenceSeconds": divergence / wav_rate,
            "referenceRms": rms(reference),
            "workloadRms": rms(workload),
            "referenceLogisticModelOffset": logistic_model_offset(reference, 3.9, 0.37),
        }


class ChaosOscRealtimeOptInContractTests(unittest.TestCase):
    """Fast, audio-free checks that the audition is opt-in but never skips once enabled."""

    def run_audition_in_child(self, overrides):
        environment = os.environ.copy()
        environment.pop(OPT_IN_VARIABLE, None)
        environment.update(overrides)
        environment["PYTHONDONTWRITEBYTECODE"] = "1"
        return subprocess.run(
            [
                sys.executable,
                "-m",
                "unittest",
                "-v",
                "test_chaososc_realtime.ChaosOscRealtimeAuditionTests",
            ],
            cwd=TEST_DIR,
            env=environment,
            capture_output=True,
            text=True,
            timeout=60,
        )


    def test_device_names_that_could_reach_a_shell_are_rejected(self):
        for name in ("Speakers `touch x`", "Speakers $(id)", 'Say "hi"',
                     "Back\\slash", "Ctl\x07"):
            with self.subTest(name=name):
                with self.assertRaises(AssertionError):
                    validate_device_name(name)
        self.assertEqual(
            validate_device_name("MacBook Neo Speakers"), "MacBook Neo Speakers"
        )

    def test_audition_is_skipped_unless_explicitly_enabled(self):
        for overrides in ({}, {OPT_IN_VARIABLE: "0"}, {OPT_IN_VARIABLE: ""}):
            with self.subTest(overrides=overrides):
                result = self.run_audition_in_child(overrides)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn("skipped", result.stderr)
                self.assertIn(OPT_IN_VARIABLE + "=1", result.stderr)

    def test_enabled_audition_fails_instead_of_skipping_without_runtime(self):
        valid_executable = shutil.which("bash")
        self.assertIsNotNone(valid_executable, "the test requires bash on PATH")
        for variable in ("SCLANG", "SCSYNTH"):
            with self.subTest(variable=variable):
                overrides = {
                    OPT_IN_VARIABLE: "1",
                    "SCLANG": valid_executable,
                    "SCSYNTH": valid_executable,
                }
                overrides[variable] = "/definitely-missing-" + variable.lower()
                result = self.run_audition_in_child(overrides)
                self.assertNotEqual(result.returncode, 0, result.stderr)
                self.assertNotIn("skipped", result.stderr)
                self.assertIn("FAILED", result.stderr)
                self.assertIn(variable + "=/definitely-missing-", result.stderr)
                self.assertIn("PATH", result.stderr)

    def test_cleanup_kills_only_scsynth_processes_on_the_audition_port(self):
        port = find_free_udp_port()
        impostor = subprocess.Popen(
            ["bash", "-c", 'exec -a "scsynth -u {}" sleep 60'.format(port)],
            start_new_session=True,
        )
        bystander = subprocess.Popen(
            ["bash", "-c", "sleep 60; : /opt/scsynth -u {}".format(port)],
            start_new_session=True,
        )
        try:
            deadline = time.monotonic() + 5
            while not find_audition_processes(port) and time.monotonic() < deadline:
                time.sleep(0.05)
            killed = kill_audition_processes(port)
            self.assertEqual([pid for pid, _command in killed], [impostor.pid])
            self.assertEqual(impostor.wait(timeout=5), -signal.SIGKILL)
            self.assertEqual(find_audition_processes(port), [])
            self.assertIsNone(bystander.poll(), "an unrelated process was killed")
        finally:
            for process in (impostor, bystander):
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except (ProcessLookupError, PermissionError):
                    pass
                process.wait()

    def test_server_output_scan_flags_failures_but_not_benign_lines(self):
        flagged = [
            "FAILURE IN SERVER /s_new SynthDef not found",
            "*** ERROR: SynthDef djmbChaosOscRtVoice not found",
            "exception in GraphDef_Recv: UGen 'ChaosOsc' not installed.",
            "ERROR: Message '+' not understood.",
            "exception in real time: alloc failed",
            "late 0.012345678",
            "DJMB_RT FAIL watchdog expired",
        ]
        benign = [
            "DJMB_RT BOOTED serverRunning=true latency=0.2",
            "SuperCollider 3 server ready.",
            "Server 'djmbChaosOscRealtime' exited with exit code 0.",
        ]
        self.assertEqual(find_forbidden_output("\n".join(flagged + benign)), flagged)


if __name__ == "__main__":
    unittest.main()
