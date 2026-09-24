#!/usr/bin/env bash
# Builds the ChaosOsc SuperCollider server plugin (Source/ChaosOsc.cpp) as a
# real, loadable shared library against the actual, pinned SuperCollider
# plugin API headers (fetched on demand by fetch_sc_plugin_api.py -- see that
# script for why headers are fetched rather than vendored).
#
# What this proves: the UGen C++ source is a syntactically and semantically
# valid consumer of the real SC_PlugIn.hpp interface at the exact commit
# pinned in IMPLEMENTATION_PLAN.md, and produces a shared library exporting
# the plugin's load entry point, matching what scsynth's plugin loader scans
# for (see supercollider's PluginLoad(name) macro / server plugin loading in
# WritingUGens.schelp).
#
# What this does NOT prove, because scsynth/sclang are not installed in this
# development environment: that scsynth actually loads and runs this plugin
# at audio-rate/control-rate without dropouts, that NRT rendering with it
# succeeds, or ABI compatibility with a real scsynth build on any platform.
# Those remain open verification tasks (see RALPH_PROGRESS.md).
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
plugin_root="$(cd "${script_dir}/../.." && pwd)"
sc_api_cache="${plugin_root}/.sc-plugin-api-cache"
bin_dir="${script_dir}/.build"
mkdir -p "${bin_dir}"

python3 "${plugin_root}/fetch_sc_plugin_api.py"

out_lib="${bin_dir}/ChaosOsc.scx"

"${CXX:-clang++}" -std=c++17 -Wall -Wextra -O2 -fPIC -shared \
    -I "${sc_api_cache}/include/plugin_interface" \
    -I "${sc_api_cache}/include/common" \
    "${script_dir}/../Source/ChaosOsc.cpp" \
    -o "${out_lib}"

echo "Built shared plugin library: ${out_lib}"

# The plugin loader looks up a load function whose symbol name is derived
# from the PluginLoad(ChaosOscUGens) macro argument, expanded by SC_PlugIn.h
# to `load(ChaosOscUGens)`; confirm the exported symbol is present so a
# missing/garbled PluginLoad invocation is caught here rather than only at
# scsynth load time.
if command -v nm >/dev/null 2>&1; then
    if nm -gU "${out_lib}" 2>/dev/null | grep -q "load(ChaosOscUGens)"; then
        echo "Verified exported plugin load symbol: load(ChaosOscUGens)"
    else
        echo "ERROR: expected exported symbol 'load(ChaosOscUGens)' not found in ${out_lib}" >&2
        nm -gU "${out_lib}" 2>/dev/null | grep -i load || true
        exit 1
    fi
else
    echo "WARNING: 'nm' not available; skipping exported-symbol check." >&2
fi
