#!/usr/bin/env python3
"""Opt-in screenshot capture for docs/VISUAL_TEST_PLAN.md (macOS only).

Launches sclang with an isolated HOME, runs tests/mb_gui/visual_scenario.scd
(which opens the real agent window through MaxxedBeats.gui with offline fake
services and drives its widgets), and captures the native window with
`screencapture -l <window id>` at each step. Screenshots are written to the
output folder (default tests/.build/mb-gui-screens/<timestamp>) and must
still be inspected by a person or agent; capturing is not visual sign-off.
The terminal needs macOS Screen Recording permission. Not run by unittest.

    python3 tests/mb_gui/capture_screenshots.py [--out DIR] [--sclang PATH]
"""

import argparse
import ctypes
import ctypes.util
import datetime
import os
from pathlib import Path
import subprocess
import sys
import threading
import time


ROOT = Path(__file__).resolve().parents[2]
SCENARIO = ROOT / "tests" / "mb_gui" / "visual_scenario.scd"
DEFAULT_SCLANG = "/Applications/SuperCollider.app/Contents/MacOS/sclang"


class _CoreGraphics:
    """Minimal ctypes access to CGWindowListCopyWindowInfo (no PyObjC)."""

    UTF8 = 0x08000100
    SINT64 = 4
    DOUBLE = 13
    ON_SCREEN_ONLY = 1
    EXCLUDE_DESKTOP = 16

    def __init__(self):
        self.cg = ctypes.cdll.LoadLibrary(ctypes.util.find_library("CoreGraphics"))
        self.cf = ctypes.cdll.LoadLibrary(ctypes.util.find_library("CoreFoundation"))
        vp, cl = ctypes.c_void_p, ctypes.c_long
        self.cg.CGWindowListCopyWindowInfo.restype = vp
        self.cg.CGWindowListCopyWindowInfo.argtypes = [ctypes.c_uint32, ctypes.c_uint32]
        self.cf.CFArrayGetCount.restype = cl
        self.cf.CFArrayGetCount.argtypes = [vp]
        self.cf.CFArrayGetValueAtIndex.restype = vp
        self.cf.CFArrayGetValueAtIndex.argtypes = [vp, cl]
        self.cf.CFDictionaryGetValue.restype = vp
        self.cf.CFDictionaryGetValue.argtypes = [vp, vp]
        self.cf.CFStringCreateWithCString.restype = vp
        self.cf.CFStringCreateWithCString.argtypes = [vp, ctypes.c_char_p, ctypes.c_uint32]
        self.cf.CFNumberGetValue.restype = ctypes.c_bool
        self.cf.CFNumberGetValue.argtypes = [vp, ctypes.c_int, vp]
        self.cf.CFRelease.argtypes = [vp]
        self.keys = {
            name: self.cf.CFStringCreateWithCString(None, name.encode(), self.UTF8)
            for name in ("kCGWindowOwnerPID", "kCGWindowNumber", "kCGWindowLayer",
                         "kCGWindowBounds", "Width", "Height")
        }

    def _number(self, dictionary, key, kind):
        ref = self.cf.CFDictionaryGetValue(dictionary, self.keys[key])
        if not ref:
            return None
        value = ctypes.c_double() if kind == self.DOUBLE else ctypes.c_int64()
        self.cf.CFNumberGetValue(ref, kind, ctypes.byref(value))
        return value.value

    def largest_window_of(self, pid):
        windows = self.cg.CGWindowListCopyWindowInfo(self.ON_SCREEN_ONLY | self.EXCLUDE_DESKTOP, 0)
        best = None
        try:
            for index in range(self.cf.CFArrayGetCount(windows)):
                info = self.cf.CFArrayGetValueAtIndex(windows, index)
                if self._number(info, "kCGWindowOwnerPID", self.SINT64) != pid:
                    continue
                if self._number(info, "kCGWindowLayer", self.SINT64) != 0:
                    continue
                bounds = self.cf.CFDictionaryGetValue(info, self.keys["kCGWindowBounds"])
                area = 0
                if bounds:
                    area = (self._number(bounds, "Width", self.DOUBLE) or 0) * (
                        self._number(bounds, "Height", self.DOUBLE) or 0)
                number = self._number(info, "kCGWindowNumber", self.SINT64)
                if best is None or area > best[0]:
                    best = (area, number)
        finally:
            self.cf.CFRelease(windows)
        return None if best is None else int(best[1])


def isolated_environment(out_dir):
    home = ROOT / "tests" / ".build" / "mb-gui-visual" / "home"
    home.mkdir(parents=True, exist_ok=True)
    environment = os.environ.copy()
    environment.update({
        "HOME": str(home),
        "XDG_CONFIG_HOME": str(home / ".config"),
        "XDG_DATA_HOME": str(home / ".local" / "share"),
        "MB_VISUAL_OUT": str(out_dir),
        "MB_VISUAL_EXIT": "1",
    })
    return environment


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--out", help="output folder for PNG screenshots")
    parser.add_argument("--sclang", default=os.environ.get("SCLANG", DEFAULT_SCLANG))
    parser.add_argument("--timeout", type=float, default=180.0)
    args = parser.parse_args(argv)
    if sys.platform != "darwin":
        print("capture_screenshots.py uses macOS screencapture; on Windows run "
              "tests/mb_gui/visual_scenario.scd from SCIDE and capture the window "
              "with the Snipping Tool (see docs/VISUAL_TEST_PLAN.md).", file=sys.stderr)
        return 2
    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    out_dir = Path(args.out) if args.out else ROOT / "tests" / ".build" / "mb-gui-screens" / stamp
    out_dir.mkdir(parents=True, exist_ok=True)
    graphics = _CoreGraphics()

    process = subprocess.Popen(
        [args.sclang, "--include-path", str(ROOT / "extension" / "Classes"), str(SCENARIO)],
        cwd=str(ROOT), env=isolated_environment(out_dir), stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, errors="replace",
    )
    timer = threading.Timer(args.timeout, process.kill)
    timer.start()
    captured, problems = [], []
    try:
        for line in process.stdout:
            line = line.strip()
            if line.startswith("MB_CAPTURE_READY "):
                name = line.split(" ", 1)[1]
                window = None
                for _ in range(50):
                    window = graphics.largest_window_of(process.pid)
                    if window is not None:
                        break
                    time.sleep(0.1)
                target = out_dir / (name + ".png")
                if window is None:
                    problems.append("{}: no on-screen sclang window found".format(name))
                else:
                    result = subprocess.run(
                        ["screencapture", "-x", "-o", "-l", str(window), str(target)],
                        capture_output=True, text=True, timeout=30)
                    if result.returncode or not target.is_file():
                        problems.append("{}: screencapture failed: {}".format(name, result.stderr.strip()))
                    else:
                        captured.append(target)
                (out_dir / (name + ".ack")).write_text("ok", encoding="utf-8")
            elif line.startswith(("MB_VISUAL_ERROR", "MB_VISUAL_TIMEOUT", "ERROR:")):
                problems.append(line)
            elif line == "MB_VISUAL_DONE":
                break
        process.wait(timeout=30)
    finally:
        timer.cancel()
        if process.poll() is None:
            process.kill()
            process.wait()
        for ack in out_dir.glob("*.ack"):
            ack.unlink()
    for path in captured:
        print("captured", path)
    for problem in problems:
        print("PROBLEM", problem, file=sys.stderr)
    print("{} screenshot(s) in {}; inspect them before recording any visual result.".format(
        len(captured), out_dir))
    return 1 if problems or not captured else 0


if __name__ == "__main__":
    sys.exit(main())
