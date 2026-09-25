#!/usr/bin/env python3
"""Exercise the plugin smoke build's symbol check without compiling or fetching."""

from __future__ import annotations

import os
import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BUILD_SCRIPT = ROOT / "plugin" / "ChaosOsc" / "Tests" / "build_plugin_smoke_test.sh"

_BASH_HARNESS = r"""
python3() { return 0; }
mock_compiler() { return 0; }
uname() { printf '%s\n' "${MOCK_UNAME:?}"; }
nm() {
    if [[ "${MOCK_ENFORCE_NM_FLAGS:-0}" == "1" ]]; then
        case "${MOCK_UNAME}" in
            Darwin)
                if [[ "${1-}" != "-gU" ]]; then
                    printf 'mock nm: expected -gU, received %s\n' "$*" >&2
                    return 64
                fi
                shift
                ;;
            *)
                if [[ "${1-}" != "-g" || "${2-}" != "--defined-only" ]]; then
                    printf 'mock nm: expected -g --defined-only, received %s\n' "$*" >&2
                    return 64
                fi
                shift 2
                ;;
        esac
        if [[ "$#" -ne 1 ]]; then
            printf 'mock nm: expected one library path, received %s arguments\n' "$#" >&2
            return 65
        fi
    fi
    if [[ "${MOCK_NM_STATUS:-0}" != "0" ]]; then
        printf 'mock nm failure with status %s\n' "${MOCK_NM_STATUS}" >&2
        return "${MOCK_NM_STATUS}"
    fi
    printf '%s\n' "${MOCK_NM_OUTPUT-}"
}
CXX=mock_compiler
source "$1"
"""


class PluginSmokeSymbolCheckTests(unittest.TestCase):
    def run_smoke(
        self,
        platform: str,
        nm_output: str = "",
        nm_status: int = 0,
        enforce_nm_flags: bool = False,
    ) -> subprocess.CompletedProcess[str]:
        env = os.environ.copy()
        env.update(
            {
                "MOCK_UNAME": platform,
                "MOCK_NM_OUTPUT": nm_output,
                "MOCK_NM_STATUS": str(nm_status),
                "MOCK_ENFORCE_NM_FLAGS": "1" if enforce_nm_flags else "0",
            }
        )
        return subprocess.run(
            ["bash", "-c", _BASH_HARNESS, "plugin-smoke-test", str(BUILD_SCRIPT)],
            cwd=ROOT,
            env=env,
            capture_output=True,
            check=False,
            text=True,
        )

    def test_accepts_the_darwin_load_export(self) -> None:
        result = self.run_smoke(
            "Darwin",
            "0000000000001234 T _load",
            enforce_nm_flags=True,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("Verified exported plugin load symbol: _load", result.stdout)

    def test_accepts_the_unprefixed_windows_load_export(self) -> None:
        result = self.run_smoke(
            "MINGW64_NT-10.0-22631",
            "0000000000001234 T load",
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("Verified exported plugin load symbol: load", result.stdout)

    def test_accepts_the_unprefixed_elf_load_export(self) -> None:
        result = self.run_smoke(
            "Linux",
            "0000000000001234 T load",
            enforce_nm_flags=True,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_uses_defined_only_nm_flags_for_windows(self) -> None:
        result = self.run_smoke(
            "MINGW64_NT-10.0-22631",
            "0000000000001234 T load",
            enforce_nm_flags=True,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_rejects_similar_but_not_exact_load_symbol(self) -> None:
        result = self.run_smoke(
            "MINGW64_NT-10.0-22631",
            "0000000000001234 T prefix_load",
        )
        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_rejects_undefined_load_symbol(self) -> None:
        result = self.run_smoke("Darwin", "                 U _load")
        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_reports_nm_invocation_failure(self) -> None:
        result = self.run_smoke("Darwin", nm_status=23)
        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("'nm' invocation failed with status 23", result.stderr)
        self.assertIn("mock nm failure with status 23", result.stderr)


if __name__ == "__main__":
    unittest.main()
