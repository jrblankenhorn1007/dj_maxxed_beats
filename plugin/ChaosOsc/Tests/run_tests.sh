#!/usr/bin/env bash
# Builds and runs the ChaosOsc DSP-core unit tests.
#
# The core (Source/ChaosOscCore.hpp) has no SuperCollider dependency, so this
# script only needs a C++17 compiler. It verifies the pure DSP core and
# per-sample block helper without requiring sclang/scsynth. The separate
# build_plugin_smoke_test.sh checks the C++ wrapper against pinned API headers;
# loading and rendering still require a SuperCollider runtime.
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
bin_dir="${script_dir}/.build"
mkdir -p "${bin_dir}"

bin="${bin_dir}/test_chaos_osc_core"

"${CXX:-clang++}" -std=c++17 -Wall -Wextra -Werror -O2 \
    "${script_dir}/test_chaos_osc_core.cpp" \
    -o "${bin}"

"${bin}"
