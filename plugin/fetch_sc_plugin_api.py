#!/usr/bin/env python3
"""Fetches the read-only SuperCollider server plugin API headers (the
public, documented interface a plugin builds against: SC_PlugIn.hpp and its
transitive local includes) at the exact commit pinned in
IMPLEMENTATION_PLAN.md (`ea52528`), so plugin sources can be compiled
against the real interface without a full local SuperCollider source
checkout or build.

These headers are NOT vendored into this repository: this script downloads
them into a gitignored cache directory (plugin/.sc-plugin-api-cache/) that
plugin build scripts fetch on demand (skipping files already cached). This
keeps the repository free of upstream GPL-3.0 source files while still
letting plugin C++ be compiled and smoke-tested against the exact pinned
public interface. It never writes to, or depends on, the sibling
`supercollider/` reference checkout, which remains read-only and is not
required for this script to work.

Usage: python3 plugin/fetch_sc_plugin_api.py
Requires network access to raw.githubusercontent.com.
"""
import os
import re
import sys
import urllib.request

SC_COMMIT = "ea52528"
BASE_URL = f"https://raw.githubusercontent.com/supercollider/supercollider/{SC_COMMIT}/"

# The only two directories the plugin-facing interface headers live in at
# this commit; local #include "X.h" directives are resolved relative to the
# including file's own directory first, then against these.
SEARCH_DIRS = [
    "include/plugin_interface/",
    "include/common/",
]

ENTRY_POINTS = [
    "include/plugin_interface/SC_PlugIn.hpp",
    "include/plugin_interface/SC_PlugIn.h",
]

INCLUDE_RE = re.compile(r'#include\s+"([^"]+)"')


def cache_dir():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(script_dir, ".sc-plugin-api-cache")


def fetch(rel_path, dest_root):
    dest = os.path.join(dest_root, rel_path)
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    url = BASE_URL + rel_path
    with urllib.request.urlopen(url, timeout=20) as resp:
        data = resp.read()
    with open(dest, "wb") as f:
        f.write(data)
    return data.decode("utf-8", errors="replace")


def main():
    dest_root = cache_dir()
    os.makedirs(dest_root, exist_ok=True)

    seen = set()
    missing = []
    to_fetch = list(ENTRY_POINTS)

    while to_fetch:
        rel = to_fetch.pop()
        if rel in seen:
            continue
        seen.add(rel)

        cached_path = os.path.join(dest_root, rel)
        if os.path.isfile(cached_path):
            with open(cached_path, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
        else:
            content = fetch(rel, dest_root)
            if content is None:
                missing.append(rel)
                continue
            print(f"fetched: {rel}")

        rel_dir = os.path.dirname(rel) + "/"
        for m in INCLUDE_RE.finditer(content):
            inc = m.group(1)
            for candidate_dir in [rel_dir] + SEARCH_DIRS:
                candidate = os.path.normpath(candidate_dir + inc)
                if candidate not in seen:
                    to_fetch.append(candidate)

    resolved = seen - set(missing)
    print("")
    print(f"SC plugin API header cache ready at: {dest_root}")
    print(f"Resolved {len(resolved)} header file(s).")

    if "include/plugin_interface/SC_PlugIn.hpp" not in resolved:
        print("ERROR: the required entry point SC_PlugIn.hpp did not resolve.",
              file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
