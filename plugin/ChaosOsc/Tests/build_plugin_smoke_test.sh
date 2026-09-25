#!/usr/bin/env bash
# Builds the ChaosOsc SuperCollider server plugin (Source/ChaosOsc.cpp) as a
# real, loadable shared library against the actual, pinned SuperCollider
# plugin API headers (fetched on demand by fetch_sc_plugin_api.py -- see that
# script for why headers are fetched rather than vendored).
#
# What this proves: the UGen C++ source is a syntactically and semantically
# valid consumer of the real SC_PlugIn.hpp interface at the exact commit
# pinned in docs/IMPLEMENTATION_PLAN.md, and produces a shared library
# exporting the platform-specific load entry point (`_load` on Mach-O, `load`
# on ELF and Windows x64), matching what scsynth's plugin loader scans for
# (see supercollider's PluginLoad(name) macro / server plugin loading in
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

has_defined_global_text_symbol() {
    local expected_symbol="$1"
    local symbol_table="$2"

    printf '%s\n' "${symbol_table}" \
        | tr -d '\r' \
        | awk -v expected="${expected_symbol}" \
            'NF >= 2 && $(NF - 1) == "T" && $NF == expected { found = 1 }
             END { exit !found }'
}

# The plugin loader looks up the C-linkage symbols PluginLoad(ChaosOscUGens)
# expands to (see SC_InterfaceTable.h): the exported `load` entry point
# (plus `api_version`/`server_type`), not a symbol containing the macro
# argument. Mach-O tools show the leading ABI underscore; ELF and Windows
# x64 tools report the unprefixed name. Inspect only global, defined symbols
# and require the exact global-text entry point.
if ! command -v nm >/dev/null 2>&1; then
    echo "ERROR: 'nm' is not available; cannot verify the exported plugin load symbol." >&2
    exit 1
fi

if [[ "$(uname -s)" == "Darwin" ]]; then
    nm_flags=(-gU)
    load_symbol="_load"
else
    nm_flags=(-g --defined-only)
    load_symbol="load"
fi

if nm_output="$(nm "${nm_flags[@]}" "${out_lib}" 2>&1)"; then
    if has_defined_global_text_symbol "${load_symbol}" "${nm_output}"; then
        echo "Verified exported plugin load symbol: ${load_symbol}"
    else
        echo "ERROR: expected defined text symbol '${load_symbol}' not found in ${out_lib}" >&2
        if [[ -n "${nm_output}" ]]; then
            printf '%s\n' "${nm_output}" | grep -i load >&2 || true
        fi
        exit 1
    fi
else
    nm_status=$?
    echo "ERROR: nm invocation failed with exit status ${nm_status} for ${out_lib}" >&2
    if [[ -n "${nm_output}" ]]; then
        printf '%s\n' "${nm_output}" >&2
    fi
    exit "${nm_status}"
fi
