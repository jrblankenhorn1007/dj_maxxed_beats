"""Offline contract checks for the versioned agent instruction Markdown."""

from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]
AGENT_DIR = ROOT / "agent"
REQUIRED_INSTRUCTIONS = (
    "ROLE.md",
    "WORKFLOW.md",
    "SUPERCOLLIDER.md",
    "SAFETY.md",
)


class AgentInstructionContractTests(unittest.TestCase):
    def read_instruction(self, name):
        path = AGENT_DIR / name
        self.assertTrue(
            path.is_file(),
            f"required versioned agent instruction is missing: {path.relative_to(ROOT)}",
        )
        if not path.is_file():
            return ""
        content = path.read_text(encoding="utf-8")
        self.assertTrue(content.strip(), f"agent instruction is empty: {name}")
        return " ".join(content.lower().split())

    def assert_mentions_all(self, document, requirements):
        for requirement in requirements:
            with self.subTest(requirement=requirement):
                self.assertIn(requirement, document)

    def test_all_four_versioned_instruction_files_exist(self):
        for name in REQUIRED_INSTRUCTIONS:
            with self.subTest(name=name):
                self.assertTrue(
                    (AGENT_DIR / name).is_file(),
                    f"required versioned agent instruction is missing: agent/{name}",
                )

    def test_representative_requests_are_explicitly_covered(self):
        workflow = self.read_instruction("WORKFLOW.md")
        scenarios = {
            "new sketch": "not writing or evaluating it",
            "tempo change": "preserve its other musical choices",
            "instrumentation change": "preserving unrelated arrangement details",
            "fix an error": (
                "separate diagnosis from a fix that has actually been tested"
            ),
            "explain code": "without modifying project files",
            "export": "request approval before rendering",
        }
        for request, expected_behavior in scenarios.items():
            with self.subTest(request=request):
                self.assertIn(request, workflow)
                self.assertIn(expected_behavior, workflow)

    def test_generated_edits_and_renders_require_review_and_approval(self):
        workflow = self.read_instruction("WORKFLOW.md")
        self.assert_mentions_all(
            workflow,
            (
                "show the complete diff",
                "after reviewing it",
                "explicit approval",
                "before applying",
                "before evaluating",
                "before rendering",
            ),
        )

    def test_supercollider_guidance_matches_the_verified_chaososc_contract(self):
        supercollider = self.read_instruction("SUPERCOLLIDER.md")
        self.assert_mentions_all(
            supercollider,
            (
                "3.14.1",
                "chaososc.ar(chaosamount, seed, freq, mul, add)",
                "chaososc.kr(chaosamount, seed, freq, mul, add)",
                "`inf`",
                "bit-identical",
                "control-rate",
                "once per output sample",
                "linearly interpolate",
                "holds the current value",
                "nan",
                "not zero-mean",
                "leakdc.ar",
                "seed is captured when the synth is created",
                "do not invent",
            ),
        )
        self.assertNotIn("planned update-rate control", supercollider)

    def test_structured_response_format_is_documented(self):
        workflow = self.read_instruction("WORKFLOW.md")
        self.assert_mentions_all(
            workflow,
            (
                "exactly one json object",
                '"maxxedbeats.proposal/1"',
                '"plan"',
                '"summary"',
                '"uncertainty"',
                '"questions"',
                '"edits"',
                '"create"',
                '"replace"',
                '"edit"',
                '"oldtext"',
                "occurs exactly once",
                '"entry"',
                '"render"',
                '"seed"',
                "never use absolute paths",
                "separately approves any render",
            ),
        )

    def test_renderable_composition_contract_is_documented(self):
        supercollider = self.read_instruction("SUPERCOLLIDER.md")
        self.assert_mentions_all(
            supercollider,
            (
                "separate headless `sclang`",
                "returns a `score`",
                "\\d_recv",
                "~mbrender",
                "do not boot a server",
                "render ends exactly at that duration",
                "silence, and clipping",
            ),
        )

    def test_safety_prevents_false_success_and_credential_disclosure(self):
        safety = self.read_instruction("SAFETY.md")
        self.assert_mentions_all(
            safety,
            (
                "never claim an operation succeeded",
                "api keys",
                "source control",
                "not a sandbox",
            ),
        )
        self.assertRegex(safety, r"\blogs?\b")
        self.assertRegex(safety, r"\bproject files?\b")

    def test_instruction_files_contain_no_api_key_like_literal(self):
        key_pattern = re.compile(r"\bsk-[a-z0-9][a-z0-9_-]{15,}\b", re.IGNORECASE)
        for name in REQUIRED_INSTRUCTIONS:
            with self.subTest(name=name):
                self.assertIsNone(
                    key_pattern.search(self.read_instruction(name)),
                    f"provider API key-like literal found in agent/{name}",
                )


if __name__ == "__main__":
    unittest.main()
