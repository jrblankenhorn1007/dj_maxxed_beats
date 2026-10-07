"""Contract test for .github/workflows/assistant-tests.yml, which runs the
MaxxedBeats assistant suites (tests/test_mb_*.py) headlessly on macOS and
Windows with the same pinned, SHA-256-verified SuperCollider 3.14.1 builds
as the existing workflows."""

from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / ".github" / "workflows"
WORKFLOW = WORKFLOWS / "assistant-tests.yml"


def pinned(path, url_name, sha_name):
    source = path.read_text(encoding="utf-8")
    url = re.search(url_name + r'="([^"]+)"', source).group(1)
    sha = re.search(sha_name + r'="([0-9a-f]{64})"', source).group(1)
    return url, sha


class AssistantWorkflowContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = WORKFLOW.read_text(encoding="utf-8")

    def test_parses_as_yaml_when_pyyaml_is_available(self):
        try:
            import yaml
        except ImportError:
            self.skipTest("PyYAML is not installed")
        document = yaml.safe_load(self.source)
        triggers = document.get("on", document.get(True))
        for trigger in ("push", "pull_request", "workflow_dispatch"):
            self.assertIn(trigger, triggers)
        self.assertEqual(document["permissions"], {"contents": "read"})
        job = document["jobs"]["assistant-tests"]
        systems = [entry["os"] for entry in job["strategy"]["matrix"]["include"]]
        self.assertTrue(any(name.startswith("macos-") for name in systems), systems)
        self.assertTrue(any(name.startswith("windows-") for name in systems), systems)
        self.assertFalse(job["strategy"]["fail-fast"])

    def test_triggers_and_least_privilege(self):
        for text in ("push:", "pull_request:", "workflow_dispatch:", "contents: read"):
            with self.subTest(text=text):
                self.assertIn(text, self.source)

    def test_reuses_the_pinned_supercollider_downloads_with_sha256_checks(self):
        mac = pinned(WORKFLOWS / "headless-tests.yml", "dmg_url", "expected_sha256")
        windows = pinned(WORKFLOWS / "plugin-builds.yml", "zip_url", "expected_sha256")
        for value in mac + windows:
            with self.subTest(value=value):
                self.assertIn(value, self.source)
        self.assertIn("shasum -a 256 --check", self.source)
        self.assertIn("sha256sum --check", self.source)
        self.assertIn("Version-3.14.1", self.source)

    def test_runs_the_assistant_suites_headlessly_with_both_executables(self):
        self.assertIn("python -m unittest discover -s tests -p 'test_mb_*.py'", self.source)
        for name in ("SCLANG=", "SCSYNTH=", "Contents/MacOS/sclang", "sclang.exe", "scsynth.exe"):
            with self.subTest(name=name):
                self.assertIn(name, self.source)
        self.assertIn("PYTHONWARNINGS: error", self.source)
        self.assertIn('python-version: "3.12"', self.source)

    def test_installs_and_uninstalls_with_the_combined_installer(self):
        self.assertIn("python scripts/install_maxxedbeats.py --extensions-dir", self.source)
        self.assertIn("python scripts/install_maxxedbeats.py --uninstall", self.source)
        self.assertIn(".maxxedbeats-install-marker", self.source)
        self.assertIn(".chaososc-install-marker", self.source)

    def test_uses_no_secrets_or_live_provider_credentials(self):
        self.assertNotIn("secrets.", self.source)
        self.assertNotRegex(self.source, r"(?i)(openai|anthropic)_api_key")


if __name__ == "__main__":
    unittest.main()
