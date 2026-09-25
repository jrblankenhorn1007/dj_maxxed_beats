#!/usr/bin/env bash
# Builds the ChaosOsc SuperCollider server plugin (Source/ChaosOsc.cpp) as a
# real, loadable shared library against the actual, pinned SuperCollider
# plugin API headers (fetched on demand by fetch_sc_plugin_api.py -- see that
# script for why headers are fetched rather than vendored).
#
# What this proves: the UGen C++ source is a syntactically and semantically
# valid consumer of the real SC_PlugIn.hpp interface at the exact commit
# pinned in docs/IMPLEMENTATION_PLAN.md, and produces a shared library exporting
# the plugin's load entry point, matching what scsynth's plugin loader scans
# for (see supercollider's PluginLoad(name) macro / server plugin loading in
# WritingUGens.schelp).
#
# What this does NOT prove: that scsynth actually loads and runs this plugin
# at audio-rate/control-rate without dropouts, that NRT rendering with it
# succeeds, or ABI compatibility with an installed server. The separate
# tests/test_chaososc_nrt.py integration test exercises loading and NRT
# rendering when a matching SuperCollider runtime is available.
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
plugin_root="$(cd "${script_dir}/../.." && pwd)"
sc_api_commit="426edf6d8742e1cc3bd85b51ca0c4e595d37a903"
sc_api_cache="${plugin_root}/.sc-plugin-api-cache/${sc_api_commit}"
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

# The plugin loader looks up the C-linkage symbols PluginLoad(ChaosOscUGens)
# expands to (see SC_InterfaceTable.h): the exported `load` entry point
# (plus `api_version`/`server_type`), not a symbol containing the macro
# argument. `nm` spells that symbol `_load` on Darwin and `load` on ELF/COFF;
# confirm the exact entry point is present so a missing/garbled PluginLoad
# invocation is caught here rather than only at scsynth load time.
if command -v nm >/dev/null 2>&1; then
    if ! nm_output="$(nm -gU "${out_lib}" 2>/dev/null)"; then
        echo "ERROR: 'nm -gU' failed to inspect ${out_lib}" >&2
        exit 1
    fi

    load_symbol="$(
        printf '%s\n' "${nm_output}" |
            awk '{ sub(/\r$/, "", $NF); if ($NF == "_load" || $NF == "load") { print $NF; exit } }'
    )"
    if [[ -n "${load_symbol}" ]]; then
        echo "Verified exported plugin load symbol: ${load_symbol}"
    else
        printf "ERROR: expected exported symbol 'load' or '_load' not found in %s\n" \
            "${out_lib}" >&2
        printf '%s\n' "${nm_output}" | grep -i load || true
        exit 1
    fi
else
    echo "WARNING: 'nm' not available; skipping exported-symbol check." >&2
fi
