import os
from pathlib import Path
import shutil
import subprocess
import unittest


ROOT = Path(__file__).resolve().parents[1]
ENTRYPOINT = ROOT / "scripts" / "run_headless_tests.sh"
WORKFLOW = ROOT / ".github" / "workflows" / "headless-tests.yml"
SC_DMG_URL = (
    "https://github.com/supercollider/supercollider/releases/download/"
    "Version-3.14.1/SuperCollider-3.14.1-macOS-universal.dmg"
)
SC_DMG_SHA256 = (
    "ed264b32752d27fc86e506dd0a7eb36de7c19ebce73c3fdf2ed5514f8c73f02e"
)


class HeadlessTestPipelineContractTests(unittest.TestCase):
    def _read_required_file(self, path, missing_message):
        self.assertTrue(path.is_file(), missing_message)
        return path.read_text(encoding="utf-8")

    def test_entrypoint_runs_cpp_tests_and_discovers_all_python_tests(self):
        source = self._read_required_file(
            ENTRYPOINT,
            "missing required entrypoint scripts/run_headless_tests.sh",
        )

        self.assertIn("plugin/ChaosOsc/Tests/run_tests.sh", source)
        self.assertIn("python3 -m unittest discover -s tests", source)
        self.assertIn("-p 'test_*.py'", source)
        self.assertTrue((ROOT / "tests" / "test_chaososc_nrt.py").is_file())

    def test_missing_runtime_tools_fail_with_actionable_diagnostics(self):
        self._read_required_file(
            ENTRYPOINT,
            "missing required entrypoint scripts/run_headless_tests.sh",
        )
        valid_executable = shutil.which("bash")
        self.assertIsNotNone(valid_executable, "the test requires bash on PATH")

        for variable, missing_path in (
            ("SCLANG", "/definitely-missing-sclang"),
            ("SCSYNTH", "/definitely-missing-scsynth"),
        ):
            with self.subTest(variable=variable):
                environment = os.environ.copy()
                environment.update(
                    {
                        "SCLANG": valid_executable,
                        "SCSYNTH": valid_executable,
                        variable: missing_path,
                    }
                )
                result = subprocess.run(
                    ["bash", str(ENTRYPOINT)],
                    cwd=ROOT,
                    env=environment,
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
                diagnostic = result.stdout + result.stderr

                self.assertNotEqual(result.returncode, 0)
                self.assertIn(variable, diagnostic)
                self.assertIn("PATH", diagnostic)

    def test_github_actions_pins_cli_runtime_and_runs_the_same_entrypoint(self):
        source = self._read_required_file(
            WORKFLOW,
            "missing required workflow .github/workflows/headless-tests.yml",
        )

        for trigger in ("pull_request:", "push:", "workflow_dispatch:"):
            with self.subTest(trigger=trigger):
                self.assertIn(trigger, source)

        self.assertIn("runs-on: macos-", source)
        self.assertIn(SC_DMG_URL, source)
        self.assertIn(SC_DMG_SHA256, source)
        self.assertIn("Contents/MacOS/sclang", source)
        self.assertIn("Contents/Resources/scsynth", source)
        self.assertIn("bash scripts/run_headless_tests.sh", source)


if __name__ == "__main__":
    unittest.main()
