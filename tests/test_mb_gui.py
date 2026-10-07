"""Headless tests for the MaxxedBeats agent window (extension/Classes/GUI).

The sclang scripts under tests/mb_gui build the real Qt window around
MBGuiController with deterministic fake services (no provider calls, no
keys, no renders), drive the widgets' actions, and print one line per check.
HOME/XDG/LOCALAPPDATA/APPDATA are isolated so the user's SuperCollider
configuration is never touched.
"""

import os
from pathlib import Path
import re
import shutil
import subprocess
import unittest


ROOT = Path(__file__).resolve().parents[1]
CLASSES = ROOT / "extension" / "Classes"
GUI_CLASSES = CLASSES / "GUI"
ENTRY_CLASS = CLASSES / "MaxxedBeats.sc"
HELP_SOURCE = ROOT / "extension" / "HelpSource"
SCRIPTS = ROOT / "tests" / "mb_gui"
BUILD_DIR = ROOT / "tests" / ".build" / "mb-gui"
LINE = re.compile(r"MBTEST (PASS|FAIL) (\S+)(?: :: (.*))?$")
DONE = re.compile(r"MBTEST DONE passes=(\d+) failures=(\d+)")


def resolve_sclang():
    configured = os.environ.get("SCLANG")
    if configured:
        candidate = Path(configured)
        if not candidate.is_absolute():
            candidate = ROOT / candidate
        if candidate.is_file():
            return str(candidate.resolve())
        resolved = shutil.which(configured)
        if resolved:
            return resolved
        raise AssertionError("SCLANG does not name an executable: " + configured)
    resolved = shutil.which("sclang")
    if resolved:
        return resolved
    raise AssertionError("sclang is required (or set SCLANG)")


def isolated_environment(name):
    home = BUILD_DIR / name / "home"
    temp = BUILD_DIR / name / "tmp"
    for directory in (home, temp):
        directory.mkdir(parents=True, exist_ok=True)
    environment = os.environ.copy()
    environment.update(
        {
            "HOME": str(home),
            "TMPDIR": str(temp),
            "XDG_CONFIG_HOME": str(home / ".config"),
            "XDG_DATA_HOME": str(home / ".local" / "share"),
            "LOCALAPPDATA": str(home / "AppData" / "Local"),
            "APPDATA": str(home / "AppData" / "Roaming"),
        }
    )
    return environment


def sclang_string(path):
    return '"' + str(path).replace("\\", "/").replace('"', '\\"') + '"'


def run_sclang_script(name, script, include_paths, timeout=None):
    """Run `script` through a wrapper that always exits sclang, even when the
    script fails to parse or throws (sclang otherwise waits for input)."""
    timeout = timeout or float(os.environ.get("MB_TEST_TIMEOUT", "240"))
    wrapper = BUILD_DIR / name / "run.scd"
    wrapper.parent.mkdir(parents=True, exist_ok=True)
    wrapper.write_text(
        "(\n"
        "try { thisProcess.interpreter.executeFile(" + sclang_string(script) + ") }\n"
        '{ |error| ("MBTEST FAIL script/uncaught :: " ++ error.errorString).postln };\n'
        '"MBTEST SCRIPT_RETURNED".postln;\n'
        "1.exit;\n"
        ")\n",
        encoding="utf-8",
    )
    command = [resolve_sclang()]
    for path in include_paths:
        command += ["--include-path", str(path)]
    command.append(str(wrapper))
    try:
        result = subprocess.run(
            command,
            cwd=str(ROOT),
            env=isolated_environment(name),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as error:
        output = error.stdout or ""
        if isinstance(output, bytes):
            output = output.decode("utf-8", "replace")
        raise AssertionError(
            "sclang timed out after {} s (class library compile error?):\n{}".format(
                timeout, "\n".join(output.splitlines()[-60:])
            )
        )
    return result.stdout + result.stderr + "\n[sclang exit code {}]".format(result.returncode)


def parse_results(output):
    passes, failures, done = [], [], None
    for raw in output.splitlines():
        line = raw.strip()
        match = LINE.search(line)
        if match:
            (passes if match.group(1) == "PASS" else failures).append(
                (match.group(2), match.group(3) or "")
            )
            continue
        match = DONE.search(line)
        if match:
            done = (int(match.group(1)), int(match.group(2)))
    return passes, failures, done


def unexpected_errors(output):
    """sclang output without known environmental noise: on hosted Windows
    runners sclang cannot bind its UDP port ("No networking: unable to bind
    udp socket") and then reports `_GetLangPort` failing at startup."""
    text = output.replace("ERROR: Message", "")
    if "No networking: unable to bind udp socket" in text:
        text = text.replace("ERROR: Primitive '_GetLangPort' failed.", "")
    return text


class SclangScriptCase(unittest.TestCase):
    script = None
    include_paths = (CLASSES,)
    minimum_passes = 1

    def run_script(self):
        output = run_sclang_script(
            self.script.stem, self.script, self.include_paths
        )
        passes, failures, done = parse_results(output)
        tail = "\n".join(output.splitlines()[-60:])
        self.assertIsNotNone(done, "script did not finish:\n" + tail)
        for name, detail in failures:
            with self.subTest(check=name):
                self.fail(detail)
        self.assertEqual(done, (len(passes), len(failures)),
                         "\n".join(line for line in output.splitlines() if "FAIL" in line or "ERROR" in line))
        self.assertGreaterEqual(len(passes), self.minimum_passes, tail)
        self.assertNotIn("ERROR:", unexpected_errors(output), tail)
        return passes


class GuiStateTests(SclangScriptCase):
    script = SCRIPTS / "gui_state_tests.scd"
    minimum_passes = 150

    def test_agent_window_state_machine_with_fake_services(self):
        self.run_script()


class EntryPointAndFactoryTests(SclangScriptCase):
    script = SCRIPTS / "entry_tests.scd"
    include_paths = (CLASSES, SCRIPTS / "stubs")
    minimum_passes = 20

    def test_entry_point_and_service_factory_follow_the_contract(self):
        self.run_script()


class GuiSourceSafetyTests(unittest.TestCase):
    def gui_sources(self):
        sources = sorted(GUI_CLASSES.glob("*.sc")) + [ENTRY_CLASS]
        self.assertTrue(len(sources) >= 5, sources)
        return {path.name: path.read_text(encoding="utf-8") for path in sources}

    def test_gui_never_evaluates_code_itself(self):
        forbidden = re.compile(
            r"\.interpret\b|interpretPrint|executeFile|\.compile\b|\.load\b|"
            r"thisProcess\.interpreter|\.loadPaths\b"
        )
        for name, source in self.gui_sources().items():
            with self.subTest(file=name):
                self.assertIsNone(forbidden.search(source))

    def test_gui_never_posts_to_the_post_window(self):
        posting = re.compile(r"\.post(ln|f|cs)?\b|\bpostln\(|\.dump\b")
        for name, source in self.gui_sources().items():
            with self.subTest(file=name):
                self.assertIsNone(posting.search(source))

    def test_choose_your_dj_label_is_present(self):
        sources = "\n".join(self.gui_sources().values())
        self.assertIn('"Choose your DJ"', sources)

    def test_help_files_exist_for_the_entry_point(self):
        self.assertTrue((HELP_SOURCE / "Classes" / "MaxxedBeats.schelp").is_file())
        self.assertTrue((HELP_SOURCE / "Guides" / "MaxxedBeats-Assistant.schelp").is_file())


if __name__ == "__main__":
    unittest.main()
