import os
from pathlib import Path
import subprocess
import unittest


ROOT = Path(__file__).resolve().parents[1]
SMOKE_SCRIPT = (
    ROOT / "plugin" / "ChaosOsc" / "Tests" / "build_plugin_smoke_test.sh"
)


class PluginSmokeSymbolCheckTests(unittest.TestCase):
    def run_smoke_check(self, nm_output, nm_status=0):
        """Run the production smoke script offline with tool commands mocked."""
        environment = os.environ.copy()
        environment["CXX"] = ":"
        environment["FAKE_NM_OUTPUT"] = nm_output
        environment["FAKE_NM_STATUS"] = str(nm_status)
        environment["PLUGIN_SMOKE_SCRIPT"] = str(SMOKE_SCRIPT)

        # The build script's first python3 call is only the header fetcher.
        # Export shell functions into the child Bash process so it cannot
        # contact the network or invoke a real compiler; nm still exercises
        # the production script's actual symbol-matching logic.
        command = r"""
python3() { return 0; }
nm() {
    if [ "$#" -ne 2 ] || [ "$1" != "-gU" ]; then
        printf 'unexpected nm arguments: %s\n' "$*" >&2
        return 97
    fi
    if [ "${FAKE_NM_STATUS:-0}" -ne 0 ]; then
        printf 'mock nm failure\n' >&2
        return "$FAKE_NM_STATUS"
    fi
    printf '%s\n' "$FAKE_NM_OUTPUT"
}
export -f python3 nm
exec bash "$PLUGIN_SMOKE_SCRIPT"
"""
        return subprocess.run(
            ["bash", "-c", command],
            cwd=ROOT,
            env=environment,
            capture_output=True,
            text=True,
            timeout=20,
        )

    def test_accepts_darwin_prefixed_loader_symbol(self):
        result = self.run_smoke_check("0000000100002ab0 T _load")

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(
            "Verified exported plugin load symbol: _load",
            result.stdout,
        )

    def test_accepts_elf_unprefixed_loader_symbol(self):
        result = self.run_smoke_check("0000000000002ab0 T load")

        self.assertEqual(
            result.returncode,
            0,
            "ELF nm output with the C-linkage load symbol was rejected:\n"
            + result.stderr,
        )
        self.assertIn(
            "Verified exported plugin load symbol: load",
            result.stdout,
        )

    def test_accepts_windows_x64_unprefixed_loader_symbol(self):
        result = self.run_smoke_check("0000000140002ab0 T load")

        self.assertEqual(
            result.returncode,
            0,
            "Windows x64 nm output with the C-linkage load symbol was rejected:\n"
            + result.stderr,
        )
        self.assertIn(
            "Verified exported plugin load symbol: load",
            result.stdout,
        )

    def test_accepts_windows_nm_output_with_crlf_line_ending(self):
        result = self.run_smoke_check("0000000140002ab0 T load\r\n")

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(
            "Verified exported plugin load symbol: load",
            result.stdout,
        )

    def test_rejects_symbols_that_only_contain_load_as_a_substring(self):
        result = self.run_smoke_check(
            "0000000000002ab0 T load_helper\n"
            "0000000000002ac0 T _load_helper\n"
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("ERROR:", result.stderr)

    def test_reports_nm_invocation_failure(self):
        result = self.run_smoke_check("", nm_status=23)

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("ERROR: 'nm -gU' failed", result.stderr)


if __name__ == "__main__":
    unittest.main()
