#!/usr/bin/env python3
"""Fetches the read-only SuperCollider server plugin API headers (the
public, documented interface a plugin builds against: SC_PlugIn.hpp and its
transitive local includes) at the SuperCollider 3.14.1 release commit pinned
in docs/IMPLEMENTATION_PLAN.md, so plugin sources can be compiled against the
real interface without a full local SuperCollider source checkout or build.

These headers are NOT vendored into this repository: this script downloads
them into a gitignored, revision-scoped cache directory
(plugin/.sc-plugin-api-cache/<commit>) that plugin build scripts fetch on
demand (skipping files already cached for that commit). This keeps the
repository free of upstream GPL-3.0 source files while still letting plugin
C++ be compiled and smoke-tested against the exact pinned public interface.
It never writes to, or depends on, the sibling `supercollider/` reference
checkout, which remains read-only and is not required for this script to work.

Usage: python3 plugin/fetch_sc_plugin_api.py
Requires network access to raw.githubusercontent.com.
"""
import os
import posixpath
import re
import sys
import urllib.error
import urllib.request

SC_COMMIT = "426edf6d8742e1cc3bd85b51ca0c4e595d37a903"
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

INCLUDE_RE = re.compile(r'#\s*include\s+"([^"]+)"')


def cache_dir():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(script_dir, ".sc-plugin-api-cache", SC_COMMIT)


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

    resolved = resolve_headers(dest_root)

    print("")
    print(f"SC plugin API header cache ready at: {dest_root}")
    print(f"Resolved {len(resolved)} header file(s).")

    if "include/plugin_interface/SC_PlugIn.hpp" not in resolved:
        print("ERROR: the required entry point SC_PlugIn.hpp did not resolve.",
              file=sys.stderr)
        return 1
    return 0


def resolve_headers(dest_root):
    """Breadth-first resolve ENTRY_POINTS and their transitive local
    `#include "X.h"` directives into dest_root, trying each of
    [including file's own dir] + SEARCH_DIRS as a candidate location for
    every include (local includes are not otherwise resolvable from raw
    GitHub content alone). Only one candidate directory actually holds each
    header upstream, so every other candidate legitimately 404s; those are
    swallowed here and do not abort resolution. Any other error (timeout,
    DNS failure, non-404 HTTP status) is a genuine outage and is
    propagated rather than being treated the same as a missing candidate.
    Returns the set of relative header paths that were resolved.
    """
    seen = set()
    resolved = set()
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
            try:
                content = fetch(rel, dest_root)
            except urllib.error.HTTPError as e:
                if e.code == 404:
                    # This candidate location doesn't exist upstream; a
                    # sibling candidate_dir may still resolve the include.
                    continue
                raise
            print(f"fetched: {rel}")

        resolved.add(rel)
        rel_dir = os.path.dirname(rel) + "/"
        for m in INCLUDE_RE.finditer(content):
            inc = m.group(1)
            for candidate_dir in [rel_dir] + SEARCH_DIRS:
                # Header paths are URL path fragments, not local filesystem
                # paths; keep their separators portable to Windows.
                candidate = posixpath.normpath(candidate_dir + inc)
                if candidate not in seen:
                    to_fetch.append(candidate)

    return resolved


if __name__ == "__main__":
    sys.exit(main())
