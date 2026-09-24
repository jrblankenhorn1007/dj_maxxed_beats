#!/usr/bin/env bash
# Builds and runs the ChaosOsc DSP-core unit tests.
#
# The core (Source/ChaosOscCore.hpp) has no SuperCollider dependency, so this
# script only needs a C++17 compiler. It does not require sclang/scsynth or a
# SuperCollider plugin build environment, which are not assumed to be
# installed in every development environment. The SC plugin wrapper and its
# NRT/real-time integration tests are added in a later iteration once that
# build environment is verified.
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
bin_dir="${script_dir}/.build"
mkdir -p "${bin_dir}"

bin="${bin_dir}/test_chaos_osc_core"

"${CXX:-clang++}" -std=c++17 -Wall -Wextra -O2 \
    "${script_dir}/test_chaos_osc_core.cpp" \
    -o "${bin}"

"${bin}"
