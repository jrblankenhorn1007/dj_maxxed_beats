#!/usr/bin/env bash
# Run dependency-light source checks and warning-free C++ builds.
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd "${script_dir}/.." && pwd)"
cd "${repo_root}"

printf '==> Bash syntax checks\n'
bash -n \
    scripts/run_quality_checks.sh \
    scripts/run_headless_tests.sh \
    plugin/ChaosOsc/Tests/run_tests.sh \
    plugin/ChaosOsc/Tests/build_plugin_smoke_test.sh

printf '\n==> Python syntax checks\n'
python_cache_dir="${repo_root}/tests/.build/python-cache"
mkdir -p "${python_cache_dir}"
PYTHONPYCACHEPREFIX="${python_cache_dir}" \
    python3 -m compileall -q -f plugin/fetch_sc_plugin_api.py tests

if ! command -v nm >/dev/null 2>&1; then
    printf "ERROR: 'nm' is required to verify the plugin load symbol.\n" >&2
    exit 1
fi

clangxx="${CLANGXX:-clang++}"
if ! command -v "${clangxx}" >/dev/null 2>&1; then
    printf "ERROR: Clang C++ analyzer is required but unavailable: %s\n" \
        "${clangxx}" >&2
    exit 1
fi

printf '\n==> Clang static analysis: ChaosOsc DSP tests\n'
"${clangxx}" -std=c++17 -Wall -Wextra -Werror --analyze \
    -Xanalyzer -analyzer-output=text \
    plugin/ChaosOsc/Tests/test_chaos_osc_core.cpp

printf '\n==> Warning-free ChaosOsc DSP unit build and tests\n'
bash plugin/ChaosOsc/Tests/run_tests.sh

printf '\n==> ChaosOsc plugin analysis and warning-free build\n'
bash plugin/ChaosOsc/Tests/build_plugin_smoke_test.sh
