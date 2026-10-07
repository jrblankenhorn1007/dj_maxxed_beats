"""MBVariationSession: the user-started, bounded in-app sampling loop."""

import json
import unittest

from mb_workflow.harness import (
    ScenarioTestCase,
    ensure_plugin_built,
    new_work_dir,
    resolve_executable,
    run_scenario,
)


ORIGINAL = "// original\n(\nScore([])\n)\n"
VARIATION = """// Variation {number}
(
var settings = ~mbRender ? (duration: 2, seed: 0.5);
var def = SynthDef(\\mbVariation{number}, {{ |out = 0, seed = 0.5|
    var chaos = LeakDC.ar(ChaosOsc.ar({chaos}, seed));
    Out.ar(out, (SinOsc.ar({freq} * (1 + (chaos * 0.01))) * 0.2) ! 2);
}});
Score([
    [0.0, [\\d_recv, def.asBytes]],
    [0.0, [\\s_new, \\mbVariation{number}, 1000, 0, 0, \\seed, settings[\\seed]]]
])
)
"""


def variation_response(number):
    return json.dumps(
        {
            "format": "maxxedbeats.proposal/1",
            "plan": "Variation {}: a darker ChaosOsc drone.".format(number),
            "summary": "Rewrites comp.scd as variation {}.".format(number),
            "uncertainty": ["Not auditioned"],
            "edits": [
                {
                    "path": "comp.scd",
                    "action": "replace",
                    "newText": VARIATION.format(
                        number=number, chaos=3.6 + number * 0.05, freq=110 * number
                    ),
                }
            ],
            "entry": "comp.scd",
            "render": {"duration": 2, "sampleRate": 48000, "numChannels": 2},
            "seed": 0.5,
        }
    )


class MBVariationSessionTests(ScenarioTestCase):
    @classmethod
    def setUpClass(cls):
        plugin_dir = ensure_plugin_built()
        sclang = resolve_executable("SCLANG", "sclang")
        scsynth = resolve_executable("SCSYNTH", "scsynth")
        work = new_work_dir("variation")
        project = work / "project"
        project.mkdir()
        (project / "comp.scd").write_text(ORIGINAL)
        (project / "notes.md").write_text("notes\n")
        responses = work / "responses"
        responses.mkdir()
        for number in range(1, 7):
            (responses / "var{}.txt".format(number)).write_text(variation_response(number))
        (responses / "malformed.txt").write_text('{"format": "maxxedbeats.proposal/1", "plan":')
        cls.scenario_run = run_scenario(
            "variation_scenario", work, (plugin_dir, sclang, scsynth), timeout=600
        )

    def test_scenario_completed_without_failures(self):
        self.assertScenarioCompleted()

    def test_session_is_user_started_and_bounded(self):
        self.assertChecks(
            "default_cap_is_four",
            "nothing_runs_before_user_starts",
            "session_completes",
            "session_stops_at_cap",
            "session_cannot_restart",
            "cap_is_bounded",
        )

    def test_candidates_are_isolated_with_fixed_seeds(self):
        self.assertChecks(
            "seeds_are_fixed_and_deterministic",
            "each_request_uses_its_fixed_seed",
            "candidates_keep_code_seed_settings_and_isolated_workspace",
            "original_project_untouched_by_session",
            "session_record_written",
            "original_still_untouched",
        )

    def test_rendering_candidates(self):
        self.assertChecks(
            "candidate_render_requires_approval",
            "candidate_render_on_request",
            "rendered_session_completes",
            "rendered_candidates_have_audio_and_checks",
            "rendered_session_keeps_original_untouched",
        )

    def test_stop_early_and_failures(self):
        self.assertChecks(
            "stop_early_ends_session",
            "stop_is_idempotent",
            "stop_cancels_in_flight_request",
            "bad_candidate_is_recorded_and_counted",
            "failed_candidate_cannot_be_applied",
            "provider_error_ends_session",
        )

    def test_apply_selected_candidate_only_after_confirmation(self):
        self.assertChecks(
            "apply_candidate_requires_confirmation",
            "apply_unknown_candidate_rejected",
            "confirmed_apply_copies_selected_candidate",
            "applied_candidate_can_be_undone",
        )


if __name__ == "__main__":
    unittest.main()
