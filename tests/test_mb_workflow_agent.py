"""MBAgent: system prompt, selected context, strict structured-response validation."""

import json
import unittest

from mb_workflow.harness import ScenarioTestCase, new_work_dir, run_scenario


COMP = "// comp\n~tempo = 100;\n(\n~mbRender.postln;\n)\n"
SKETCH = (
    "// sketch\n(\nvar def = SynthDef(\\mbSketch, { |out = 0|\n"
    "    Out.ar(out, LeakDC.ar(ChaosOsc.ar(3.8, 0.42)) * 0.1 ! 2)\n});\n"
    "Score([[0.0, [\\d_recv, def.asBytes]], [0.1, [\\s_new, \\mbSketch, 1000, 0, 0]]])\n)\n"
)
VALID_EDITS = [
    {"path": "comp.scd", "action": "edit", "oldText": "~tempo = 100;", "newText": "~tempo = 120;"},
    {"path": "sketch.scd", "action": "create", "newText": SKETCH},
]
INVALID_JSON = {
    "trailing_comma": '{"a": 1,}',
    "duplicate_key": '{"a": 1, "a": 2}',
    "leading_zero": '{"a": 01}',
    "single_quotes": "{'a': 1}",
    "unterminated": '{"a": "abc',
    "lone_surrogate": '"\\ud800"',
    "comment": '{"a": 1} // note',
    "two_values": "{} {}",
    "raw_control": '"a\tb"',
    "too_deep": "[" * 40 + "]" * 40,
    "nan": '{"a": NaN}',
    "bad_escape": '"\\x41"',
}
RESPONSE_CASES = (
    "malformed", "prose", "empty", "array", "wrong_format", "unknown_key",
    "missing_plan", "outside_path", "absolute_path", "data_dir_path",
    "too_many_edits", "secret", "oversized", "bad_seed", "bad_render",
    "duplicate_paths", "bad_entry", "stale_old_text", "edits_not_array",
    "number_as_text",
)


def proposal(edits, **extra):
    document = {
        "format": "maxxedbeats.proposal/1",
        "plan": "Intro, pulse, and outro at 120 BPM with a ChaosOsc drone.",
        "summary": "Raises the tempo and adds a ChaosOsc sketch.",
        "assumptions": ["Stereo output"],
        "uncertainty": ["Not auditioned"],
        "questions": [],
        "edits": edits,
    }
    document.update(extra)
    return json.dumps(document, indent=2)


def write_fixtures(work):
    project = work / "project"
    project.mkdir()
    (project / "comp.scd").write_text(COMP)
    (project / "unselected.scd").write_text("// UNSELECTED-MARKER\n")
    (project / "notes.md").write_text("notes\n")
    (work / "outside-context.scd").write_text("// outside context\n")

    json_dir = work / "json"
    (json_dir / "invalid").mkdir(parents=True)
    nested = {"a": [1, 2.5, -3e2, True, False, None], "b": {"c": 'x"y\\n\u00e9\U0001F3B5'}}
    (json_dir / "nested.json").write_text(json.dumps(nested, ensure_ascii=True))
    (json_dir / "expected_c.txt").write_bytes(nested["b"]["c"].encode("utf-8"))
    for name, text in INVALID_JSON.items():
        (json_dir / "invalid" / (name + ".json")).write_text(text)

    valid = proposal(
        VALID_EDITS,
        entry="sketch.scd",
        render={"duration": 12, "sampleRate": 48000, "numChannels": 2},
        seed=0.42,
    )
    unknown = json.loads(proposal(VALID_EDITS))
    unknown["notes"] = "extra"
    missing_plan = json.loads(proposal(VALID_EDITS))
    del missing_plan["plan"]
    fake_key = "sk-" + "Ab1" * 12
    responses = {
        "valid": valid,
        "fenced": "```json\n" + valid + "\n```\n",
        "malformed": valid[: len(valid) // 2],
        "prose": "Sure! Here is the plan:\n" + valid,
        "empty": "   ",
        "array": "[1, 2]",
        "wrong_format": proposal(VALID_EDITS, format="other/2"),
        "unknown_key": json.dumps(unknown),
        "missing_plan": json.dumps(missing_plan),
        "outside_path": proposal([{"path": "../outside.scd", "action": "create", "newText": "1"}]),
        "absolute_path": proposal(
            [{"path": str(work / "outside.scd"), "action": "create", "newText": "1"}]
        ),
        "data_dir_path": proposal(
            [{"path": ".maxxedbeats/x.scd", "action": "create", "newText": "1"}]
        ),
        "too_many_edits": proposal(
            [
                {"path": "many{}.scd".format(index), "action": "create", "newText": "1"}
                for index in range(17)
            ]
        ),
        "secret": proposal(
            [{"path": "sketch.scd", "action": "create", "newText": "~key = \"" + fake_key + "\";"}]
        ),
        "oversized": proposal(VALID_EDITS, plan="x" * 600000),
        "bad_seed": proposal(VALID_EDITS, seed=2),
        "bad_render": proposal(VALID_EDITS, render={"duration": 12, "sampleRate": 1234}),
        "duplicate_paths": proposal(
            [
                VALID_EDITS[0],
                {"path": "comp.scd", "action": "replace", "newText": "// other\n"},
            ]
        ),
        "bad_entry": proposal(VALID_EDITS, entry="notes.md"),
        "stale_old_text": proposal(
            [{"path": "comp.scd", "action": "edit", "oldText": "~tempo = 99;", "newText": "x"}]
        ),
        "edits_not_array": proposal({}),
        "number_as_text": proposal([{"path": "sketch.scd", "action": "create", "newText": 42}]),
    }
    response_dir = work / "responses"
    response_dir.mkdir()
    for name, text in responses.items():
        (response_dir / (name + ".txt")).write_text(text)


class MBAgentWorkflowTests(ScenarioTestCase):
    @classmethod
    def setUpClass(cls):
        work = new_work_dir("agent")
        write_fixtures(work)
        cls.scenario_run = run_scenario("agent_scenario", work)

    def test_scenario_completed_without_failures(self):
        self.assertScenarioCompleted()

    def test_strict_json(self):
        self.assertChecks(
            "json_parses_nested_values",
            "json_roundtrips",
            "json_escapes_control_characters",
            *["json_rejects_" + name for name in INVALID_JSON]
        )

    def test_prompt_uses_instructions_and_only_selected_context(self):
        self.assertChecks(
            "system_prompt_includes_all_instructions_in_order",
            "system_prompt_documents_structured_format",
            "request_uses_selected_model_and_instructions",
            "request_includes_only_selected_context",
            "request_carries_history_seed_and_variation",
            "request_rejects_out_of_project_context",
            "request_rejects_unknown_history_role",
            "request_rejects_empty_prompt",
        )

    def test_valid_response_becomes_reviewable_proposal(self):
        self.assertChecks(
            "valid_response_becomes_proposal",
            "proposal_has_plan_summary_and_raw",
            "proposal_edits_are_reviewable",
            "proposal_reports_usage_from_meter",
            "proposal_carries_render_settings_seed_and_entry",
            "proposal_reports_provider_model_and_uncertainty",
            "propose_never_writes_files",
            "fenced_json_is_accepted",
        )

    def test_invalid_responses_are_rejected_without_side_effects(self):
        self.assertChecks(
            "rejection_detail_never_echoes_secret",
            "files_still_untouched",
            *["rejects_" + name for name in RESPONSE_CASES]
        )

    def test_provider_and_configuration_errors(self):
        self.assertChecks(
            "provider_auth_error_passes_through",
            "provider_rate_limit_passes_through",
            "missing_model_is_config_error_without_request",
            "bad_context_fails_before_any_request",
            "missing_instructions_is_config_error",
            "cancel_reports_cancelled",
        )


if __name__ == "__main__":
    unittest.main()
