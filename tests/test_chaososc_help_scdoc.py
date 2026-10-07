import os
from pathlib import Path
import shutil
import subprocess
import unittest


ROOT = Path(__file__).resolve().parents[1]
HELP_SOURCE_DIR = ROOT / "plugin" / "ChaosOsc" / "HelpSource"
CLASS_DIR = ROOT / "plugin" / "ChaosOsc" / "Classes"
BUILD_DIR = ROOT / "tests" / ".build" / "help-scdoc"


def resolve_sclang():
    configured = os.environ.get("SCLANG")
    if configured:
        candidate = Path(configured)
        if not candidate.is_absolute():
            candidate = ROOT / candidate
        if candidate.is_file():
            return str(candidate.resolve())
        resolved = shutil.which(configured)
        if resolved:
            return resolved
        raise AssertionError("SCLANG does not name an executable: " + configured)
    resolved = shutil.which("sclang")
    if resolved:
        return resolved
    raise AssertionError("sclang is required (or set SCLANG)")


def sclang_string(path):
    return '"' + str(path).replace("\\", "/").replace('"', '\\"') + '"'


class ChaosOscHelpScdocTests(unittest.TestCase):
    def test_every_help_file_parses_with_scdoc(self):
        help_files = sorted(HELP_SOURCE_DIR.rglob("*.schelp"))
        self.assertTrue(help_files, "no ChaosOsc help files found")

        BUILD_DIR.mkdir(parents=True, exist_ok=True)
        runtime_home = BUILD_DIR / "runtime-home"
        runtime_home.mkdir(parents=True, exist_ok=True)
        script = BUILD_DIR / "parse_help.scd"
        checks = "\n".join(
            "check.({});".format(sclang_string(path)) for path in help_files
        )
        script.write_text(
            "(\n"
            "var failures = 0;\n"
            "var check = { |path|\n"
            "    var tree = SCDoc.parseFileFull(path);\n"
            "    if(tree.isNil) {\n"
            "        failures = failures + 1;\n"
            '        ("SCDOC_PARSE_FAILED: " ++ path).postln;\n'
            "    } {\n"
            '        ("SCDOC_PARSE_OK: " ++ path).postln;\n'
            "    };\n"
            "};\n"
            + checks
            + "\n"
            '("SCDOC_PARSE_FAILURES: " ++ failures).postln;\n'
            "0.exit;\n"
            ")\n",
            encoding="utf-8",
        )

        environment = os.environ.copy()
        environment.update(
            {
                "HOME": str(runtime_home),
                "XDG_CONFIG_HOME": str(runtime_home / ".config"),
                "XDG_DATA_HOME": str(runtime_home / ".local" / "share"),
            }
        )
        result = subprocess.run(
            [resolve_sclang(), "--include-path", str(CLASS_DIR), str(script)],
            cwd=ROOT,
            env=environment,
            capture_output=True,
            text=True,
            timeout=120,
        )
        output = result.stdout + result.stderr
        self.assertEqual(result.returncode, 0, output)
        self.assertIn("SCDOC_PARSE_FAILURES: 0", output, output)
        self.assertNotIn("SCDOC_PARSE_FAILED", output, output)
        self.assertNotIn("syntax error", output, output)


if __name__ == "__main__":
    unittest.main()
