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
mock_analyzer() { return 0; }
mock_compiler() { return 0; }
uname() {
    if [[ "$#" -ne 1 || "$1" != "-s" ]]; then
        printf 'mock uname: expected -s, received %s\n' "$*" >&2
        return 67
    fi
    printf '%s\n' "${MOCK_UNAME:?}"
}
nm() {
    case "${MOCK_UNAME:?}" in
        Darwin)
            if [[ "$#" -ne 2 || "$1" != "-gU" ]]; then
                printf 'mock nm: expected -gU, received %s\n' "$*" >&2
                return 64
            fi
            shift
            ;;
        *)
            if [[ "$#" -ne 3 || "$1" != "-g" || "$2" != "--defined-only" ]]; then
                printf 'mock nm: expected -g --defined-only, received %s\n' "$*" >&2
                return 65
            fi
            shift 2
            ;;
    esac
    if [[ "$#" -ne 1 || "$1" != *ChaosOsc.scx ]]; then
        printf 'mock nm: expected one ChaosOsc.scx path, received %s\n' "$*" >&2
        return 66
    fi
    if [[ "${MOCK_NM_STATUS:-0}" != "0" ]]; then
        printf '%s\n' "${MOCK_NM_DIAGNOSTIC:-mock nm invocation failed}" >&2
        return "${MOCK_NM_STATUS}"
    fi
    printf '%s' "${MOCK_NM_OUTPUT-}"
}
command() {
    if [[ "${MOCK_NM_MISSING:-0}" == "1" && "$#" -eq 2 && "$1" == "-v" && "$2" == "nm" ]]; then
        return 1
    fi
    builtin command "$@"
}
CLANGXX=mock_analyzer
CXX=mock_compiler
source "$1"
"""


class PluginSmokeSymbolCheckTests(unittest.TestCase):
    def run_smoke(
        self,
        platform: str,
        nm_output: str = "",
        nm_status: int = 0,
        nm_missing: bool = False,
    ) -> subprocess.CompletedProcess[str]:
        environment = os.environ.copy()
        environment.update(
            {
                "MOCK_UNAME": platform,
                "MOCK_NM_OUTPUT": nm_output,
                "MOCK_NM_STATUS": str(nm_status),
                "MOCK_NM_DIAGNOSTIC": "mock nm could not inspect the plugin",
                "MOCK_NM_MISSING": "1" if nm_missing else "0",
            }
        )
        return subprocess.run(
            [
                "bash",
                "-c",
                _BASH_HARNESS,
                "plugin-smoke-symbol-check",
                str(BUILD_SCRIPT),
            ],
            cwd=ROOT,
            env=environment,
            capture_output=True,
            check=False,
            text=True,
            timeout=20,
        )

    def assert_verified(
        self,
        result: subprocess.CompletedProcess[str],
        symbol: str,
    ) -> None:
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        verified_lines = [
            line
            for line in result.stdout.splitlines()
            if line.startswith("Verified exported plugin load symbol:")
        ]
        self.assertEqual(
            verified_lines,
            [f"Verified exported plugin load symbol: {symbol}"],
        )

    def test_darwin_uses_mach_o_flags_and_accepts_prefixed_text_export(self) -> None:
        result = self.run_smoke(
            "Darwin",
            "0000000100001000 T _load\n",
        )

        self.assert_verified(result, "_load")

    def test_elf_uses_defined_only_flags_and_exact_global_text_export(self) -> None:
        result = self.run_smoke(
            "Linux",
            "0000000000001000 T load_helper\n"
            "0000000000000000 U load\n"
            "0000000000001100 T load\n",
        )

        self.assert_verified(result, "load")

    def test_windows_x64_uses_gnu_flags_and_accepts_unprefixed_export(self) -> None:
        result = self.run_smoke(
            "MINGW64_NT-10.0-22631",
            "0000000140001000 T load\n",
        )

        self.assert_verified(result, "load")

    def test_windows_crlf_output_accepts_the_unprefixed_export(self) -> None:
        result = self.run_smoke(
            "MINGW64_NT-10.0-22631",
            "0000000140001000 T load\r\n",
        )

        self.assert_verified(result, "load")

    def test_rejects_similar_but_not_exact_loader_names(self) -> None:
        result = self.run_smoke(
            "Darwin",
            "0000000100001000 T plugin._load\n"
            "0000000100001100 T _load_helper\n"
            "0000000100001200 T prefix_load\n",
        )

        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("ERROR:", result.stderr)
        self.assertNotIn("Verified exported plugin load symbol:", result.stdout)

    def test_rejects_an_undefined_loader_symbol(self) -> None:
        result = self.run_smoke("Darwin", "                 U _load\n")

        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("ERROR:", result.stderr)
        self.assertNotIn("Verified exported plugin load symbol:", result.stdout)

    def test_reports_nm_failure_status_and_diagnostic(self) -> None:
        result = self.run_smoke(
            "Darwin",
            nm_status=23,
        )

        self.assertEqual(result.returncode, 23, result.stdout + result.stderr)
        self.assertIn("invocation failed with status 23", result.stderr)
        self.assertIn("nm -gU", result.stderr)
        self.assertIn("mock nm could not inspect the plugin", result.stderr)

    def test_preserves_warning_when_nm_is_unavailable(self) -> None:
        result = self.run_smoke("Darwin", nm_missing=True)

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn(
            "WARNING: 'nm' not available; skipping exported-symbol check.",
            result.stderr,
        )
        self.assertNotIn("Verified exported plugin load symbol:", result.stdout)


if __name__ == "__main__":
    unittest.main()
