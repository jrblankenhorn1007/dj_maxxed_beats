"""MBRenderer: approved, isolated sclang Score build + scsynth NRT with ChaosOsc."""

import json
import os
import struct
import unittest

from mb_workflow.harness import (
    ScenarioTestCase,
    builtin_plugin_dir,
    ensure_plugin_built,
    new_work_dir,
    resolve_executable,
    run_scenario,
)


COMP = "// original composition\n(\nScore([])\n)\n"
SKETCH = """// Proposed ChaosOsc sketch
(
var settings = ~mbRender ? (duration: 4, seed: 0.37);
var def = SynthDef(\\mbTestTone, { |out = 0, seed = 0.5, amp = 0.3|
    var chaos = LeakDC.ar(ChaosOsc.ar(3.8, seed));
    var tone = SinOsc.ar(220 * (1 + (chaos * 0.01)));
    Out.ar(out, (((tone * 0.7) + (chaos * 0.2)) * amp) ! 2);
});
~leak = \\generatedCodeRan;
Score([
    [0.0, [\\d_recv, def.asBytes]],
    [0.0, [\\s_new, \\mbTestTone, 1000, 0, 0, \\seed, settings[\\seed], \\amp, 0.3]],
    [99.0, [\\n_free, 1000]]
])
)
"""
CLASSIC = """// Uses the Quark composition class; also checks process isolation.
(
if("MB_RENDER_TEST_PARENT_ONLY".getenv.notNil) { Error("parent environment leaked").throw };
if("HOME".getenv == %(parent_home)s) { Error("render shares the parent HOME").throw };
MaxxedBeatsComposition.score(~mbRender[\\duration], ~mbRender[\\seed])
)
"""
SILENT = "(\nScore([])\n)\n"
CLIP = """(
var def = SynthDef(\\mbLoud, { |out = 0| Out.ar(out, SinOsc.ar(220) * 2) });
Score([[0.0, [\\d_recv, def.asBytes]], [0.0, [\\s_new, \\mbLoud, 1000, 0, 0]]])
)
"""
COMPOSITIONS = {
    "comp.scd": COMP,
    "silent.scd": SILENT,
    "clip.scd": CLIP,
    "broken.scd": "(\nvar x = ;\nScore([])\n)\n",
    "runtime.scd": "(\nnil.mbUndefinedMethod;\nScore([])\n)\n",
    "notscore.scd": "(\n42\n)\n",
    "badevents.scd": "(\n[[\\notATime, [\\s_new]]]\n)\n",
    "hang.scd": "(\ninf.do { 1 + 1 };\nScore([])\n)\n",
    "notes.md": "notes\n",
}


def wav_data_chunk(path):
    data = path.read_bytes()
    offset = 12
    while offset + 8 <= len(data):
        name, size = struct.unpack_from("<4sI", data, offset)
        if name == b"data":
            return data[offset + 8 : offset + 8 + size]
        offset += 8 + size + (size % 2)
    raise AssertionError("no data chunk in {}".format(path))


class MBRendererWorkflowTests(ScenarioTestCase):
    @classmethod
    def setUpClass(cls):
        plugin_dir = ensure_plugin_built()
        sclang = resolve_executable("SCLANG", "sclang")
        scsynth = resolve_executable("SCSYNTH", "scsynth")
        builtin_plugin_dir(scsynth)
        work = new_work_dir("render")
        project = work / "project"
        project.mkdir()
        for name, text in COMPOSITIONS.items():
            (project / name).write_text(text)
        (project / "classic.scd").write_text(
            CLASSIC % {"parent_home": json.dumps(str(work / "home"))}
        )
        (work / "empty-plugins").mkdir()
        outside = work / "outside-render-dir"
        outside.mkdir()
        for name, relative in (("data", ".maxxedbeats"), ("renders", "renders"),
                               ("scratch", ".maxxedbeats/renders")):
            reserved_project = work / ("reserved-" + name)
            reserved = reserved_project / relative
            reserved.parent.mkdir(parents=True, exist_ok=True)
            (reserved_project / "comp.scd").write_text(COMP)
            os.symlink(str(outside), str(reserved), target_is_directory=True)
        (work / "proposal.txt").write_text(
            json.dumps(
                {
                    "format": "maxxedbeats.proposal/1",
                    "plan": "A 3 second ChaosOsc drone at 220 Hz.",
                    "summary": "Adds sketch.scd, a ChaosOsc drone.",
                    "uncertainty": ["Not auditioned"],
                    "edits": [{"path": "sketch.scd", "action": "create", "newText": SKETCH}],
                    "entry": "sketch.scd",
                    "render": {"duration": 3, "sampleRate": 48000, "numChannels": 2},
                    "seed": 0.42,
                }
            )
        )
        cls.project = project
        cls.scenario_run = run_scenario(
            "render_scenario", work, (plugin_dir, sclang, scsynth), timeout=600
        )

    def test_scenario_completed_without_failures(self):
        self.assertScenarioCompleted()

    def test_end_to_end_propose_apply_render(self):
        self.assertChecks(
            "e2e_propose",
            "e2e_confirmed_apply",
            "e2e_render_succeeds",
            "e2e_output_in_project_renders",
            "e2e_output_matches_settings",
            "e2e_checks_pass",
            "e2e_metadata_sidecar",
            "e2e_metadata_has_no_secrets_or_unknown_fields",
            "e2e_progress_reported",
            "generated_code_not_evaluated_in_user_interpreter",
            "second_render_gets_unique_name",
            "child_has_quark_and_chaososc_classes_and_isolated_env",
        )

    def test_render_requires_explicit_approval(self):
        self.assertChecks(
            "render_requires_approval",
            "render_requires_boolean_approval",
            "unapproved_render_creates_nothing",
        )

    def test_reserved_symlinks_cannot_receive_render_writes(self):
        self.assertChecks(*["render_rejects_reserved_" + name
                            for name in ("data", "renders", "scratch")])
        self.assertEqual([], list((self.scenario_run.work_dir / "outside-render-dir").iterdir()))

    def test_failures_are_actionable_and_leave_no_outputs(self):
        self.assertChecks(
            "build_failure_broken",
            "build_failure_runtime",
            "build_failure_notscore",
            "build_failure_badevents",
            "failed_renders_leave_no_outputs",
            "hung_composition_times_out",
            "missing_chaososc_plugin_is_actionable",
            "cancel_stops_render_without_outputs",
            *["invalid_request_{}".format(index) for index in range(8)]
        )

    def test_automatic_checks_flag_silence_and_clipping(self):
        self.assertChecks(
            "silent_render_is_flagged",
            "clipping_render_is_flagged_and_format_matches",
        )

    def test_same_seed_renders_are_identical(self):
        sketches = []
        for sidecar in sorted((self.project / "renders").glob("*.json")):
            metadata = json.loads(sidecar.read_text())
            if metadata.get("entry") == "sketch.scd":
                sketches.append(self.project / "renders" / metadata["output"])
        self.assertEqual(2, len(sketches), sketches)
        # Header PEAK chunks carry timestamps; the audio must be bit-identical.
        self.assertEqual(wav_data_chunk(sketches[0]), wav_data_chunk(sketches[1]))

    def test_child_processes_do_not_outlive_the_scenario(self):
        work_logs = list((self.project / ".maxxedbeats" / "renders").glob("*/sclang.log"))
        self.assertTrue(work_logs, "render work folders with logs are kept for diagnostics")
        for home in (self.project / ".maxxedbeats" / "renders").glob("*/home"):
            self.fail("isolated child HOME was not removed: {}".format(home))


if __name__ == "__main__":
    unittest.main()
