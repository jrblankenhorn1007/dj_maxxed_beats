#!/usr/bin/env bash
# Run source-quality checks and Python tests, including the real ChaosOsc NRT test.
# The NRT test needs the sclang/scsynth command-line executables; no GUI,
# real-time server, or audio device is started by this entrypoint.
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd "${script_dir}/.." && pwd)"

resolve_executable() {
    local candidate="$1"
    local variable_name="$2"
    local executable_name="$3"
    local resolved

    if [[ "${candidate}" == */* ]]; then
        if [[ "${candidate}" == /* ]]; then
            resolved="${candidate}"
        else
            resolved="${PWD}/${candidate}"
        fi
    else
        resolved="$(command -v "${candidate}" 2>/dev/null || true)"
    fi

    if [[ -z "${resolved}" || ! -f "${resolved}" || ! -x "${resolved}" ]]; then
        printf 'ERROR: %s executable is missing or not executable: %s\n' \
            "${variable_name}" "${candidate}" >&2
        printf 'Set %s to an executable path or make %s available on PATH.\n' \
            "${variable_name}" "${executable_name}" >&2
        return 1
    fi

    printf '%s\n' "${resolved}"
}

SCLANG="$(resolve_executable "${SCLANG:-sclang}" SCLANG sclang)" || exit 1
SCSYNTH="$(resolve_executable "${SCSYNTH:-scsynth}" SCSYNTH scsynth)" || exit 1
export SCLANG SCSYNTH

cd "${repo_root}"
printf 'Using SCLANG: %s\n' "${SCLANG}"
printf 'Using SCSYNTH: %s\n' "${SCSYNTH}"

test_tmp_dir="${repo_root}/tests/.build/test-tmp"
mkdir -p "${test_tmp_dir}"
export TMPDIR="${test_tmp_dir}"
export PYTHONDONTWRITEBYTECODE=1

printf '\n==> Static analysis and warning-free builds\n'
bash scripts/run_quality_checks.sh

printf '\n==> Python tests (including the ChaosOsc sclang/scsynth NRT integration)\n'
python3 -m unittest discover -s tests -p 'test_*.py' -v
