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
# argument. Mach-O prefixes C symbols with `_`; ELF and Windows x64 do not.
# Check the exact global, defined text symbol so a missing/garbled
# PluginLoad invocation is caught here rather than only at scsynth load time.
has_exported_load_symbol() {
    local symbol_listing="$1"
    local expected_symbol="$2"
    printf '%s\n' "${symbol_listing}" | awk -v expected="${expected_symbol}" '
        NF >= 2 && $NF == expected && $(NF - 1) == "T" { found = 1 }
        END { exit !found }
    '
}

if command -v nm >/dev/null 2>&1; then
    platform="$(uname -s)"
    if [[ "${platform}" == "Darwin" ]]; then
        # Mach-O adds a leading underscore to C symbols; -U omits undefineds.
        nm_args=(-gU)
        expected_load_symbol="_load"
    else
        # ELF and Windows x64 expose the C symbol without Mach-O's underscore.
        nm_args=(-g --defined-only)
        expected_load_symbol="load"
    fi

    if nm_output="$(nm "${nm_args[@]}" "${out_lib}" 2>&1)"; then
        if has_exported_load_symbol "${nm_output}" "${expected_load_symbol}"; then
            echo "Verified exported plugin load symbol: ${expected_load_symbol}"
        else
            echo "ERROR: expected exported symbol '${expected_load_symbol}' not found in ${out_lib}" >&2
            printf '%s\n' "${nm_output}" | grep -i load >&2 || true
            exit 1
        fi
    else
        nm_status=$?
        echo "ERROR: 'nm' invocation failed with status ${nm_status} for ${out_lib}" >&2
        if [[ -n "${nm_output}" ]]; then
            printf '%s\n' "${nm_output}" >&2
        fi
        exit 1
    fi
else
    echo "WARNING: 'nm' not available; skipping exported-symbol check." >&2
fi
