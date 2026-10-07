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
import tempfile
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
    try:
        result = subprocess.run(
            command,
            cwd=str(ROOT),
            env=isolated_environment(home),
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as error:
        output = error.stdout or ""
        if isinstance(output, bytes):
            output = output.decode("utf-8", "replace")
        return ScenarioRun(work_dir, output + "\nPYTHON TIMEOUT", -1)
    return ScenarioRun(work_dir, result.stdout + result.stderr, result.returncode)


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
