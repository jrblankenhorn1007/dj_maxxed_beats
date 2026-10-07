"""Run MaxxedBeats workflow scenarios in a headless, isolated sclang process.

Each scenario is an ``.scd`` file in this directory that loads
``harness.scd`` and prints ``MBTEST PASS <name>`` or
``MBTEST FAIL <name> :: <detail>`` lines followed by ``MBTEST DONE``. The
Python test cases run a scenario once per class and assert on named checks.
"""

import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import unittest


ROOT = Path(__file__).resolve().parents[2]
SCENARIO_DIR = Path(__file__).resolve().parent
EXTENSION_CLASSES = ROOT / "extension" / "Classes"
CHAOSOSC_CLASSES = ROOT / "plugin" / "ChaosOsc" / "Classes"
PLUGIN_BUILD_SCRIPT = (
    ROOT / "plugin" / "ChaosOsc" / "Tests" / "build_plugin_smoke_test.sh"
)
PLUGIN_BUILD_DIR = ROOT / "plugin" / "ChaosOsc" / "Tests" / ".build"
PLUGIN_LIBRARY = PLUGIN_BUILD_DIR / "ChaosOsc.scx"
WORK_ROOT = ROOT / "tests" / ".build" / "mb-workflow"
RESULT_PATTERN = re.compile(r"^MBTEST (PASS|FAIL) (\S+)(?: :: (.*))?$")
SECRET_VARIABLES = ("OPENAI_API_KEY", "ANTHROPIC_API_KEY")


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


def isolated_environment(home):
    environment = os.environ.copy()
    for name in SECRET_VARIABLES:
        environment.pop(name, None)
    environment.update(
        {
            "HOME": str(home),
            "XDG_CONFIG_HOME": str(home / ".config"),
            "XDG_DATA_HOME": str(home / ".local" / "share"),
            "XDG_CACHE_HOME": str(home / ".cache"),
            "LOCALAPPDATA": str(home / "AppData" / "Local"),
            "APPDATA": str(home / "AppData" / "Roaming"),
        }
    )
    return environment


def builtin_plugin_dir(scsynth):
    executable = Path(scsynth).resolve()
    for candidate in (
        executable.parent / "plugins",
        executable.parent.parent / "Resources" / "plugins",
        executable.parent.parent / "lib" / "SuperCollider" / "plugins",
    ):
        if candidate.is_dir():
            return candidate.resolve()
    raise AssertionError(
        "could not locate SuperCollider's built-in plugins next to {}".format(
            scsynth
        )
    )


def ensure_plugin_built():
    """Folder holding a ChaosOsc plugin binary for scsynth -U.

    ``MB_CHAOSOSC_PLUGIN_DIR`` may name an installed ChaosOsc folder (CI uses
    the copy installed by scripts/install_maxxedbeats.py). Otherwise POSIX
    hosts run the smoke build script and Windows builds and installs it with
    CMake/MSVC through scripts/install_chaososc.py into tests/.build.
    """
    configured = os.environ.get("MB_CHAOSOSC_PLUGIN_DIR")
    if configured:
        folder = Path(configured)
        if not folder.is_absolute():
            folder = ROOT / folder
        if not any((folder / name).is_file() for name in ("ChaosOsc.scx", "ChaosOsc.so")):
            raise AssertionError(
                "MB_CHAOSOSC_PLUGIN_DIR has no ChaosOsc plugin binary: {}".format(folder)
            )
        return folder.resolve()
    if sys.platform == "win32":
        return _build_plugin_with_installer()
    if PLUGIN_LIBRARY.is_file():
        return PLUGIN_BUILD_DIR
    WORK_ROOT.mkdir(parents=True, exist_ok=True)
    home = Path(tempfile.mkdtemp(prefix="plugin-home-", dir=str(WORK_ROOT)))
    result = subprocess.run(
        ["bash", str(PLUGIN_BUILD_SCRIPT)],
        cwd=str(ROOT),
        env=isolated_environment(home),
        capture_output=True,
        text=True,
        timeout=300,
    )
    if result.returncode or not PLUGIN_LIBRARY.is_file():
        raise AssertionError(
            "ChaosOsc plugin build failed:\n{}\n{}".format(
                result.stdout, result.stderr
            )
        )
    return PLUGIN_BUILD_DIR


def _build_plugin_with_installer():
    extensions = WORK_ROOT / "chaososc-extensions"
    folder = extensions / "ChaosOsc"
    if (folder / "ChaosOsc.scx").is_file():
        return folder
    WORK_ROOT.mkdir(parents=True, exist_ok=True)
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "install_chaososc.py"),
         "--extensions-dir", str(extensions),
         "--build-dir", str(WORK_ROOT / "chaososc-build")],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        timeout=900,
    )
    if result.returncode or not (folder / "ChaosOsc.scx").is_file():
        raise AssertionError(
            "ChaosOsc plugin build (CMake/MSVC) failed:\n{}\n{}".format(
                result.stdout, result.stderr
            )
        )
    return folder


class ScenarioRun(object):
    def __init__(self, work_dir, stdout, returncode):
        self.work_dir = work_dir
        self.stdout = stdout
        self.returncode = returncode
        self.results = {}
        for line in stdout.splitlines():
            match = RESULT_PATTERN.match(line.strip())
            if match:
                passed = match.group(1) == "PASS"
                previous = self.results.get(match.group(2), (True, ""))
                self.results[match.group(2)] = (
                    previous[0] and passed,
                    match.group(3) or previous[1],
                )
        self.done = "MBTEST DONE" in stdout


def new_work_dir(prefix):
    WORK_ROOT.mkdir(parents=True, exist_ok=True)
    return Path(tempfile.mkdtemp(prefix=prefix + "-", dir=str(WORK_ROOT)))


def run_scenario(name, work_dir, extra_args=(), timeout=600):
    return run_scenario_file(SCENARIO_DIR / (name + ".scd"), work_dir, extra_args, timeout)


def run_scenario_file(script, work_dir, extra_args=(), timeout=600):
    sclang = resolve_executable("SCLANG", "sclang")
    home = work_dir / "home"
    home.mkdir(parents=True, exist_ok=True)
    command = [
        sclang,
        "--include-path",
        str(EXTENSION_CLASSES),
        "--include-path",
        str(CHAOSOSC_CLASSES),
        str(script),
        str(work_dir),
        str(ROOT),
    ] + [str(argument) for argument in extra_args]
    output, returncode = run_like_scide(command, isolated_environment(home), timeout)
    run = ScenarioRun(work_dir, output, returncode)
    # Echo failures at once: a CI job that is cancelled later still shows them.
    failures = [line for line in output.splitlines() if line.startswith("MBTEST FAIL")]
    if failures or not run.done:
        sys.stderr.write("\n[{}] {}\n{}\n".format(
            Path(script).name, "\n".join(failures),
            "" if run.done else "did not finish; output tail:\n" + output[-4000:]))
        for log in _unfinished_render_logs(work_dir):
            sys.stderr.write("--- {} (tail)\n{}\n".format(log, log.read_text(
                encoding="utf-8", errors="replace")[-2500:]))
        sys.stderr.flush()
    return run


def _unfinished_render_logs(work_dir, limit=3):
    """Render child logs without a written Score (diagnostics only)."""
    logs = []
    for log in Path(work_dir).rglob("sclang.log"):
        try:
            if "MB_RENDER_SCORE_WRITTEN" not in log.read_text(encoding="utf-8", errors="replace"):
                logs.append(log)
        except OSError:
            pass
    return sorted(logs, key=lambda path: path.stat().st_mtime)[-limit:]


def run_like_scide(command, environment, timeout):
    """Run sclang with stdin as an open, silent pipe (as SCIDE does), so a
    child process that waits for or reads sclang's stdin hangs the test."""
    process = subprocess.Popen(
        command, cwd=str(ROOT), env=environment, stdin=subprocess.PIPE,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    chunks = {"out": [], "err": []}

    def drain(stream, key):
        for raw in iter(stream.readline, b""):
            chunks[key].append(raw.decode("utf-8", "replace"))
        stream.close()

    readers = [threading.Thread(target=drain, args=(process.stdout, "out")),
               threading.Thread(target=drain, args=(process.stderr, "err"))]
    for reader in readers:
        reader.daemon = True
        reader.start()
    timed_out = False
    try:
        process.wait(timeout)
    except subprocess.TimeoutExpired:
        timed_out = True
        process.kill()
        process.wait(30)
    for reader in readers:
        reader.join(30)
    process.stdin.close()
    output = ("".join(chunks["out"]) + "".join(chunks["err"])).replace("\r\n", "\n")
    if timed_out:
        return output + "\nPYTHON TIMEOUT", -1
    return output, process.returncode


class ScenarioTestCase(unittest.TestCase):
    """Base class: subclasses set ``scenario`` and call ``run_once``."""

    scenario = None
    scenario_run = None

    def assertChecks(self, *names):
        run = type(self).scenario_run
        for name in names:
            with self.subTest(check=name):
                self.assertIn(
                    name,
                    run.results,
                    "check {} did not run; sclang output tail:\n{}".format(
                        name, run.stdout[-4000:]
                    ),
                )
                passed, detail = run.results[name]
                self.assertTrue(passed, "{} failed: {}".format(name, detail))

    def assertScenarioCompleted(self):
        run = type(self).scenario_run
        failures = [
            "{}: {}".format(name, detail)
            for name, (passed, detail) in sorted(run.results.items())
            if not passed
        ]
        self.assertTrue(
            run.done,
            "scenario did not finish; output tail:\n{}".format(run.stdout[-6000:]),
        )
        self.assertEqual([], failures)
