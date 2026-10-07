"""Run sclang snippets headlessly with an isolated HOME and collect results.

Each snippet runs inside a Routine on AppClock. Helpers available to it:
  ~emit.(tag, value)     -> prints "MBTEST <json>" (parsed by run_sclang)
  ~await.({ |done| ...}) -> waits until done.(args...) is called, returns args
  ~errInfo.(error)       -> (kind:, detail:) for an MBError
"""

import json
import os
from pathlib import Path
import shutil
import subprocess
import threading
import time

ROOT = Path(__file__).resolve().parents[2]
BUILD_DIR = ROOT / "tests" / ".build" / "mb_providers"
CLASSES_DIR = ROOT / "extension" / "Classes"
RATES_PATH = ROOT / "extension" / "Data" / "provider-rates.json"

FAKE_KEY = "sk-test_MBfakeKEY_0123456789abcdef"
FAKE_ANTHROPIC_KEY = "sk-ant-test_MBfakeKEY_9876543210zyx"

PROLOGUE = r"""
(
~emit = { |tag, value| ("MBTEST " ++ MBJSON.encode((tag: tag.asString, value: value))).postln };
~errInfo = { |e| if(e.isKindOf(MBError)) { (kind: e.kind, detail: e.detail) } { (kind: \other, detail: e.asString) } };
~await = { |fn| var c = Condition(false), out; fn.({ |...args| out = args; c.test = true; c.signal }); c.wait; out };
~elapsed = { Main.elapsedTime };
AppClock.sched(%TIMEOUT%, { "MBTEST_TIMEOUT".postln; 1.exit; nil });
Routine({
	try {
%BODY%
		"MBTEST_DONE".postln;
		0.exit;
	} { |err|
		("MBTEST_FAILED " ++ err.errorString).postln; err.reportError;
		1.exit;
	};
}).play(AppClock);
)
"""


def resolve_sclang():
    configured = os.environ.get("SCLANG")
    if configured:
        candidate = Path(configured)
        if not candidate.is_absolute():
            candidate = ROOT / candidate
        if candidate.is_file():
            return str(candidate)
        found = shutil.which(configured)
        if found:
            return found
        raise AssertionError("SCLANG does not name an executable: " + configured)
    found = shutil.which("sclang")
    if not found:
        raise AssertionError("sclang is required (or set SCLANG)")
    return found


class SclangRun(object):
    def __init__(self, results, output, returncode, home, workdir):
        self.results = results
        self.output = output
        self.returncode = returncode
        self.home = home
        self.workdir = workdir

    def get(self, tag):
        values = [r.get("value") for r in self.results if r.get("tag") == tag]
        if not values:
            raise AssertionError(
                "no result tagged {!r}; output:\n{}".format(tag, self.output[-4000:])
            )
        return values[-1]

    def all(self, tag):
        return [r.get("value") for r in self.results if r.get("tag") == tag]


def _collect(proc, lines):
    """Read sclang output; stop it early on an uncaught error (it would idle)."""
    failing_since = None
    for raw in iter(proc.stdout.readline, b""):
        line = raw.decode("utf-8", "replace")
        lines.append(line)
        if failing_since is None and (line.startswith("ERROR:") or line.startswith("MBTEST_FAILED")):
            failing_since = time.time()
            timer = threading.Timer(1.0, lambda: proc.poll() is None and proc.kill())
            timer.daemon = True
            timer.start()
    proc.stdout.close()


def isolated_env(workdir):
    home = workdir / "home"
    tmp = workdir / "tmp"
    for path in (home, tmp, home / ".config", home / ".local" / "share",
                 home / "AppData" / "Local", home / "AppData" / "Roaming"):
        path.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env.update({
        "HOME": str(home),
        "TMPDIR": str(tmp),
        "XDG_CONFIG_HOME": str(home / ".config"),
        "XDG_DATA_HOME": str(home / ".local" / "share"),
        "LOCALAPPDATA": str(home / "AppData" / "Local"),
        "APPDATA": str(home / "AppData" / "Roaming"),
    })
    for name in ("OPENAI_API_KEY", "ANTHROPIC_API_KEY", "CURL_HOME"):
        env.pop(name, None)
    return env, home


def fresh_workdir(name):
    workdir = BUILD_DIR / name
    if workdir.exists():
        shutil.rmtree(str(workdir))
    workdir.mkdir(parents=True)
    return workdir


def run_sclang(name, body, timeout=40, workdir=None, expect_done=True):
    workdir = workdir or fresh_workdir(name)
    env, home = isolated_env(workdir)
    script = workdir / "script.scd"
    script.write_text(
        PROLOGUE.replace("%TIMEOUT%", str(timeout)).replace("%BODY%", body),
        encoding="utf-8",
    )
    proc = subprocess.Popen(
        [resolve_sclang(), "--include-path", str(CLASSES_DIR), str(script)],
        cwd=str(ROOT), env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
    )
    lines = []
    reader = threading.Thread(target=_collect, args=(proc, lines))
    reader.daemon = True
    reader.start()
    reader.join(timeout + 30)
    if proc.poll() is None:
        proc.kill()
    reader.join(5)
    proc.wait(10)
    output = "".join(lines)
    results = []
    for line in output.splitlines():
        if line.startswith("MBTEST {"):
            results.append(json.loads(line[len("MBTEST "):]))
    if expect_done and "MBTEST_DONE" not in output:
        raise AssertionError("sclang snippet did not finish:\n" + output[-6000:])
    return SclangRun(results, output, proc.returncode, home, workdir)


def sc_string(text):
    """Quote a Python string as a SuperCollider string literal."""
    return '"' + text.replace("\\", "\\\\").replace('"', '\\"') + '"'


def tree_contains(root, needle):
    """Return files under root (except the test script) containing needle."""
    hits = []
    data = needle.encode("utf-8")
    for path in Path(root).rglob("*"):
        if path.is_file() and not path.is_symlink() and path.name != "script.scd":
            try:
                if data in path.read_bytes():
                    hits.append(str(path))
            except OSError:
                pass
    return hits
