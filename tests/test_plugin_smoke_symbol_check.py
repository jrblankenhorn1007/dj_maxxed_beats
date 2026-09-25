import os
from pathlib import Path
import subprocess
import unittest


ROOT = Path(__file__).resolve().parents[1]
BUILD_DIR = ROOT / "tests" / ".build" / "plugin-smoke-symbol-check"
MOCK_BIN = BUILD_DIR / "bin"
BUILD_SCRIPT = (
    ROOT
    / "plugin"
    / "ChaosOsc"
    / "Tests"
    / "build_plugin_smoke_test.sh"
)


class PluginSmokeSymbolCheckTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Keep deterministic command shims in the project's ignored build
        # tree. The fake header fetcher and compiler make these tests
        # network-free and independent of a SuperCollider SDK.
        MOCK_BIN.mkdir(parents=True, exist_ok=True)
        cls._write_executable("python3", "#!/bin/sh\nexit 0\n")
        cls._write_executable(
            "clang++",
            """#!/bin/sh
set -eu
output=
while [ "$#" -gt 0 ]; do
    if [ "$1" = "-o" ]; then
        shift
        output="${1:?missing output path}"
        break
    fi
    shift
done
if [ -z "$output" ]; then
    printf '%s\\n' 'mock compiler did not receive -o' >&2
    exit 80
fi
printf '%s\\n' 'mock plugin library' > "$output"
""",
        )
        cls._write_executable(
            "uname",
            """#!/bin/sh
set -eu
if [ "$#" -ne 1 ] || [ "$1" != "-s" ]; then
    printf 'unexpected uname arguments: %s\\n' "$*" >&2
    exit 81
fi
printf '%s\\n' "${MOCK_UNAME_OUTPUT:?missing mock platform}"
""",
        )
        cls._write_executable(
            "nm",
            """#!/bin/sh
set -eu
case "${MOCK_NM_EXPECTED_MODE:?missing expected nm mode}" in
    darwin)
        if [ "$#" -ne 2 ] || [ "$1" != "-gU" ]; then
            printf 'unexpected Darwin nm arguments: %s\\n' "$*" >&2
            exit 82
        fi
        ;;
    gnu)
        if [ "$#" -ne 3 ] || [ "$1" != "-g" ] || [ "$2" != "--defined-only" ]; then
            printf 'unexpected GNU nm arguments: %s\\n' "$*" >&2
            exit 83
        fi
        ;;
    *)
        printf 'unexpected mock nm mode: %s\\n' "$MOCK_NM_EXPECTED_MODE" >&2
        exit 84
        ;;
esac
status="${MOCK_NM_EXIT_STATUS:-0}"
if [ "$status" -ne 0 ]; then
    printf '%s\\n' "${MOCK_NM_ERROR_OUTPUT:-mock nm invocation failed}" >&2
    exit "$status"
fi
printf '%s' "${MOCK_NM_OUTPUT-}"
""",
        )

    @staticmethod
    def _write_executable(name, contents):
        executable = MOCK_BIN / name
        executable.write_text(contents, encoding="utf-8")
        executable.chmod(0o755)

    def run_smoke_test(
        self,
        *,
        platform,
        nm_mode,
        nm_output,
        nm_exit_status=0,
        nm_error_output="mock nm invocation failed",
    ):
        environment = os.environ.copy()
        environment.update(
            {
                "PATH": os.pathsep.join(
                    [str(MOCK_BIN), environment.get("PATH", "")]
                ),
                "CXX": "clang++",
                "MOCK_UNAME_OUTPUT": platform,
                "MOCK_NM_EXPECTED_MODE": nm_mode,
                "MOCK_NM_OUTPUT": nm_output,
                "MOCK_NM_EXIT_STATUS": str(nm_exit_status),
                "MOCK_NM_ERROR_OUTPUT": nm_error_output,
                "PYTHONDONTWRITEBYTECODE": "1",
            }
        )
        return subprocess.run(
            ["bash", str(BUILD_SCRIPT)],
            cwd=ROOT,
            env=environment,
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )

    def test_darwin_accepts_the_exact_prefixed_text_export(self):
        result = self.run_smoke_test(
            platform="Darwin",
            nm_mode="darwin",
            nm_output="0000000100001000 T _load\n",
        )

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn(
            "Verified exported plugin load symbol: _load", result.stdout
        )

    def test_elf_accepts_the_exact_unprefixed_text_export(self):
        result = self.run_smoke_test(
            platform="Linux",
            nm_mode="gnu",
            nm_output=(
                "0000000000001000 T load_helper\n"
                "0000000000000000 U load\n"
                "0000000000001100 T load\n"
            ),
        )

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("Verified exported plugin load symbol: load", result.stdout)

    def test_windows_x64_accepts_unprefixed_crlf_nm_output(self):
        result = self.run_smoke_test(
            platform="MINGW64_NT-10.0-22631",
            nm_mode="gnu",
            nm_output="0000000140001000 T load\r\n",
        )

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("Verified exported plugin load symbol: load", result.stdout)

    def test_similar_symbol_name_does_not_satisfy_export_check(self):
        result = self.run_smoke_test(
            platform="Darwin",
            nm_mode="darwin",
            nm_output="0000000100001000 T plugin._load\n",
        )

        self.assertNotEqual(result.returncode, 0)

    def test_undefined_symbol_does_not_satisfy_export_check(self):
        result = self.run_smoke_test(
            platform="Darwin",
            nm_mode="darwin",
            nm_output="                 U _load\n",
        )

        self.assertNotEqual(result.returncode, 0)

    def test_nm_invocation_failure_is_reported_with_its_exit_status(self):
        result = self.run_smoke_test(
            platform="Darwin",
            nm_mode="darwin",
            nm_output="",
            nm_exit_status=23,
            nm_error_output="mock nm could not inspect the plugin",
        )

        self.assertEqual(result.returncode, 23, result.stdout + result.stderr)
        self.assertIn("nm invocation failed", result.stderr)
        self.assertIn("mock nm could not inspect the plugin", result.stderr)


if __name__ == "__main__":
    unittest.main()
