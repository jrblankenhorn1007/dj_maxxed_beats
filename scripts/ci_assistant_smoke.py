#!/usr/bin/env python3
"""Smoke test of an INSTALLED MaxxedBeats assistant (Quark + ChaosOsc).

Runs scripts/assistant_smoke.scd in sclang WITHOUT --include-path, so the
classes must come from the Extensions folder SuperCollider scans by itself
(on Windows: %LOCALAPPDATA%\\SuperCollider\\Extensions, where install.ps1 from
MaxxedBeats-Windows-x64.zip puts them). Offline and keyless: the mock DJ
proposes a ChaosOsc composition, it is applied and rendered in a separate
sclang + scsynth with the renderer's default tools and plugin paths, and the
agent window opens and closes.

Usage: python scripts/ci_assistant_smoke.py --sclang SCLANG --work-dir DIR
           [--expect-extensions-dir DIR] [--query-credential-store]
           [--home DIR]   (POSIX only: run sclang with this HOME)
Exit status 0 when every check passed.
"""

import argparse
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import threading


ROOT = Path(__file__).resolve().parents[1]
SCENARIO = ROOT / "scripts" / "assistant_smoke.scd"
RESULT = re.compile(r"^MBSMOKE (PASS|FAIL) (\S+)(?: :: (.*))?$")
REQUIRED = (
    "classes_installed", "agent_instructions_load", "platform_credential_backend",
    "mock_models", "select_model", "propose", "apply_confirmed",
    "render_with_installed_chaososc", "render_checks", "gui_opens",
)


# sclang waits in its REPL when a script names a missing class, so check the
# classes at run time before the scenario (which names them) is compiled.
BOOTSTRAP = """(
var missing = [\\MaxxedBeats, \\MBAgent, \\MBProject, \\MBRenderer, \\MBWindowsCredentialStore,
    \\ChaosOsc].reject { |name| name.asClass.notNil };
if(missing.notEmpty) {
    ("MBSMOKE FAIL classes_installed :: missing " ++ missing.join(", ")).postln;
    "MBSMOKE DONE failures=1".postln;
    1.exit;
} {
    thisProcess.interpreter.executeFile(%SCENARIO%);
};
)
"""


def sc_string(text):
    return '"' + text.replace("\\", "\\\\").replace('"', '\\"') + '"'


def parse_args(argv):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--sclang", required=True)
    parser.add_argument("--work-dir", required=True)
    parser.add_argument("--expect-extensions-dir", default="")
    parser.add_argument("--query-credential-store", action="store_true")
    parser.add_argument("--home")
    parser.add_argument("--timeout", type=float, default=900)
    return parser.parse_args(argv)


def run_like_scide(command, cwd, env, timeout):
    """Run sclang with stdin as an open, silent pipe, as SCIDE does, so a
    helper that waits for sclang's stdin makes the smoke test fail."""
    process = subprocess.Popen(command, cwd=str(cwd), env=env, stdin=subprocess.PIPE,
                               stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    chunks = []

    def drain():
        for raw in iter(process.stdout.readline, b""):
            chunks.append(raw.decode("utf-8", "replace"))
        process.stdout.close()

    reader = threading.Thread(target=drain)
    reader.daemon = True
    reader.start()
    suffix = ""
    try:
        process.wait(timeout)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(30)
        suffix = "\nPYTHON TIMEOUT"
    reader.join(30)
    process.stdin.close()
    output = "".join(chunks).replace("\r\n", "\n") + suffix
    return output, (-1 if suffix else process.returncode)


def main(argv=None):
    args = parse_args(argv)
    work = Path(args.work_dir).resolve()
    if work.exists():
        shutil.rmtree(str(work))
    work.mkdir(parents=True)
    env = os.environ.copy()
    for name in ("OPENAI_API_KEY", "ANTHROPIC_API_KEY"):
        env.pop(name, None)
    if args.home:
        env["HOME"] = str(Path(args.home).resolve())
        for name in ("XDG_CONFIG_HOME", "XDG_DATA_HOME"):
            env.pop(name, None)
    expected = str(Path(args.expect_extensions_dir).resolve()) if args.expect_extensions_dir else ""
    bootstrap = work / "bootstrap.scd"
    bootstrap.write_text(BOOTSTRAP.replace("%SCENARIO%", sc_string(str(SCENARIO))), encoding="utf-8")
    sclang = str(Path(args.sclang).resolve()) if Path(args.sclang).is_file() else args.sclang
    command = [sclang, str(bootstrap), str(work), expected,
               "1" if args.query_credential_store else "0"]
    output, code = run_like_scide(command, work, env, args.timeout)
    results = {}
    for line in output.splitlines():
        match = RESULT.match(line.strip())
        if match:
            results[match.group(2)] = (match.group(1) == "PASS", match.group(3) or "")
        if line.startswith("MBSMOKE INFO"):
            print(line)
    failed = sorted(name for name, (passed, _) in results.items() if not passed)
    missing = [name for name in REQUIRED if name not in results]
    if args.expect_extensions_dir:
        missing += [name for name in ("installed_copy_in_use", "agent_instructions_installed",
                                      "renderer_uses_installed_chaososc") if name not in results]
    if args.query_credential_store and "credential_store_query" not in results:
        missing.append("credential_store_query")
    done = "MBSMOKE DONE failures=0" in output
    for name in sorted(results):
        passed, detail = results[name]
        print("{} {}{}".format("PASS" if passed else "FAIL", name, " :: " + detail if detail else ""))
    if failed or missing or not done or code != 0:
        print("Assistant smoke test FAILED (exit {}; failed: {}; missing: {}). sclang output tail:".format(
            code, failed, missing))
        print(output[-8000:])
        return 1
    print("Assistant smoke test passed: {} checks.".format(len(results)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
