#!/usr/bin/env python3
"""Temporary CI diagnostic: how Windows PowerShell 5.1 runs the MaxxedBeats
helper under different stdin/stdout handle setups (prints a table)."""

import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))
from mb_providers.fake_server import FakeProviderServer  # noqa: E402

HELPER = ROOT / "extension" / "Data" / "windows" / "MaxxedBeatsCredential.ps1"
PS = os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "System32", "WindowsPowerShell", "v1.0", "powershell.exe")
WORK = ROOT / "build" / "helper-probe"


def drain(stream, sink):
    for raw in iter(stream.readline, b""):
        sink.append(raw.decode("utf-8", "replace"))


def probe(name, action, extra, stdin_mode, payload, inputformat=True, target="MaxxedBeatsProbe:openai"):
    run = WORK / name
    run.mkdir(parents=True, exist_ok=True)
    for child in run.iterdir():
        child.unlink()
    if action == "request":
        (run / "curl-spec.json").write_text(json.dumps(SPEC), encoding="utf-8")
    argv = [PS, "-NoLogo", "-NoProfile", "-NonInteractive"] + (["-InputFormat", "None"] if inputformat else []) + [
        "-ExecutionPolicy", "Bypass", "-File", str(HELPER), "-Action", action, "-RunDir", str(run)] + extra
    stdin = subprocess.DEVNULL if stdin_mode == "devnull" else subprocess.PIPE
    out, err = [], []
    start = time.time()
    proc = subprocess.Popen(argv, stdin=stdin, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    for stream, sink in ((proc.stdout, out), (proc.stderr, err)):
        threading.Thread(target=drain, args=(stream, sink), daemon=True).start()
    if stdin is subprocess.PIPE:
        if payload is not None:
            proc.stdin.write(payload)
            proc.stdin.flush()
        if stdin_mode == "close":
            proc.stdin.close()
    found = None
    while time.time() - start < 20:
        if (run / "exit-code.txt").exists():
            found = time.time() - start
            break
        time.sleep(0.05)
    time.sleep(0.5)
    alive = proc.poll() is None
    if alive:
        subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)], capture_output=True)
    code = (run / "exit-code.txt").read_text().strip() if found else None
    print("{:<34} exitfile={} code={} alive_after={} files={}".format(
        name, None if found is None else round(found, 2), code, alive, sorted(p.name for p in run.iterdir())))
    if err or out:
        print("    stdout:", "".join(out)[:600].replace("\n", " | "))
        print("    stderr:", "".join(err)[:1500].replace("\n", " | "))


SPEC = {}


def main():
    global SPEC
    server = FakeProviderServer()
    server.route("GET", "/v1/models", {"status": 200, "body": {"data": []}})
    curl = os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "System32", "curl.exe")
    with server:
        SPEC = {"curl": curl, "args": ["-q", "-sS", "-o", "body.txt", "-K", "-", server.base_url + "/v1/models",
                                       "--stderr", "curl-stderr.txt"], "headerPrefix": "Authorization: Bearer "}
        probe("has_devnull", "has", ["-Target", "MaxxedBeatsProbe:openai"], "devnull", None)
        probe("has_pipe_open_line", "has", ["-Target", "MaxxedBeatsProbe:openai"], "open", b"\n")
        probe("has_pipe_open_line_noIF", "has", ["-Target", "MaxxedBeatsProbe:openai"], "open", b"\n", inputformat=False)
        probe("has_pipe_open_empty", "has", ["-Target", "MaxxedBeatsProbe:openai"], "open", None)
        probe("has_pipe_closed_line", "has", ["-Target", "MaxxedBeatsProbe:openai"], "close", b"\n")
        probe("req_stdin_open_line", "request", ["-KeyFromStdin"], "open", b"sk-probe_0123456789abc\n")
        probe("req_stdin_closed_line", "request", ["-KeyFromStdin"], "close", b"sk-probe_0123456789abc\n")
        probe("req_stdin_closed_line_noIF", "request", ["-KeyFromStdin"], "close", b"sk-probe_0123456789abc\n",
              inputformat=False)
        if len(sys.argv) > 1:
            sclang_probe(sys.argv[1], server.base_url)
        print("server saw", [r["headers"].get("authorization", "")[:12] for r in server.requests])
    return 0


SC_PROBE = r"""
(
var dir = %DIR%, helper = %HELPER%, ps = %PS%, base = %BASE%, wait, t0 = Main.elapsedTime;
wait = { |path, secs| var t = 0; while { File.exists(path).not and: { t < secs } } { 0.1.wait; t = t + 0.1 }; t };
Routine { 60.do { |i| ("PROBE tick " ++ (Main.elapsedTime - t0).round(0.01)).postln; 0.5.wait } }.play(AppClock);
Routine {
	var p, t, store, oa, done = false;
	p = Pipe.argv([%CMD%, "/d", "/c", "echo hi>" ++ (dir +/+ "cmd.txt")], "w");
	("PROBE pipe_cmd open=" ++ p.isOpen ++ " waited=" ++ wait.(dir +/+ "cmd.txt", 5)).postln;
	File.mkdir(dir +/+ "h1");
	("PROBE pipe_helper_has start " ++ (Main.elapsedTime - t0).round(0.01)).postln;
	p = Pipe.argv([ps, "-NoLogo", "-NoProfile", "-NonInteractive", "-InputFormat", "None", "-ExecutionPolicy", "Bypass",
		"-File", helper, "-Action", "has", "-RunDir", dir +/+ "h1", "-Target", "MaxxedBeatsProbe:openai"], "w");
	("PROBE pipe_helper_has opened " ++ (Main.elapsedTime - t0).round(0.01)).postln;
	p.putString("\n");
	("PROBE pipe_helper_has put " ++ (Main.elapsedTime - t0).round(0.01)).postln;
	p.flush;
	("PROBE pipe_helper_has flushed " ++ (Main.elapsedTime - t0).round(0.01)).postln;
	("PROBE pipe_helper_has waited=" ++ wait.(dir +/+ "h1" +/+ "exit-code.txt", 20)).postln;
	("PROBE closing " ++ (Main.elapsedTime - t0).round(0.01)).postln;
	("PROBE closed code=" ++ p.close ++ " at " ++ (Main.elapsedTime - t0).round(0.01)).postln;
	store = MBCredentialStore.fake;
	store.storeKey(\openai, "sk-probe_0123456789abc", {}, {});
	0.2.wait;
	oa = MBOpenAIProvider.new(store, base, 5);
	t = Main.elapsedTime;
	oa.listModels({ |m| ("PROBE list ok " ++ m.size ++ " after " ++ (Main.elapsedTime - t)).postln; done = true },
		{ |e| ("PROBE list err " ++ e.kind ++ " " ++ e.detail ++ " after " ++ (Main.elapsedTime - t)).postln; done = true });
	("PROBE list returned " ++ (Main.elapsedTime - t)).postln;
	block { |break| 300.do { if(done) { break.value }; 0.1.wait } };
	t = Main.elapsedTime;
	done = false;
	MBCredentialStore.default.hasKey(\openai, { |r| ("PROBE store_has " ++ r ++ " after " ++ (Main.elapsedTime - t)).postln; done = true });
	block { |break| 300.do { if(done) { break.value }; 0.1.wait } };
	"PROBE done".postln;
	0.exit;
}.play(AppClock);
)
"""


def sclang_probe(sclang, base):
    work = WORK / "sc"
    work.mkdir(parents=True, exist_ok=True)
    quote = lambda text: '"' + str(text).replace("\\", "\\\\").replace('"', '\\"') + '"'
    script = WORK / "probe.scd"
    script.write_text(SC_PROBE.replace("%DIR%", quote(work)).replace("%HELPER%", quote(HELPER)).replace(
        "%PS%", quote(PS)).replace("%BASE%", quote(base)).replace("%CMD%", quote(os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "System32", "cmd.exe"))),
        encoding="utf-8")
    proc = subprocess.Popen([sclang, "--include-path", str(ROOT / "extension" / "Classes"), str(script)],
                            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    try:
        out = proc.communicate(timeout=200)[0]
    except subprocess.TimeoutExpired:
        proc.kill()
        out = proc.communicate()[0]
    text = out.decode("utf-8", "replace")
    print("\n".join(line for line in text.splitlines() if "PROBE" in line or "ERROR" in line or "rror" in line))


if __name__ == "__main__":
    sys.exit(main())
