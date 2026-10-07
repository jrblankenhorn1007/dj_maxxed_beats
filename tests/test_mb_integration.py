"""End-to-end integration of the MaxxedBeats assistant window with the real
provider and workflow classes (MBMockProvider, fake credential store,
isolated HOME) and real separate-process NRT renders with ChaosOsc.

The scenario (tests/mb_gui/integration_scenario.scd) opens the window with
MaxxedBeats.gui, chooses the mock DJ, proposes, reviews, confirms the apply,
approves a render, undoes, runs a two-candidate variation session with
approved renders and a confirmed apply, exercises error paths, and does a
key-management round trip. No network, no real keys.
"""

import os
from pathlib import Path
import struct
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests" / "mb_workflow"))
sys.path.insert(0, str(ROOT / "tests"))

import harness  # noqa: E402


ORIGINAL = """// Original composition (integration fixture)
(
var settings = ~mbRender ? (duration: 4, seed: 0.37);
var def = SynthDef(\\mbFixtureTone, { |out = 0, amp = 0.2|
    Out.ar(out, (SinOsc.ar(220) * amp) ! 2);
});
Score([
    [0.0, [\\d_recv, def.asBytes]],
    [0.0, [\\s_new, \\mbFixtureTone, 1000, 0, 0]]
])
)
"""
SECRET_FRAGMENT = "0123456789abcdefghij"
REQUIRED = (
    "window_open", "providers_listed", "models_refreshed", "unusable_model_labelled",
    "unusable_model_refused", "dj_selected", "project_open", "provider_failure_shown",
    "provider_failure_touches_nothing", "unavailable_model_blocks",
    "unavailable_model_touches_nothing", "proposal_arrived", "proposal_valid_format",
    "diff_shown", "usage_shown", "nothing_written_before_approval",
    "apply_needs_confirmation", "applied", "file_changed", "backup_saved",
    "render_needs_confirmation", "render_succeeded", "render_file", "render_checks",
    "render_shown", "undo_restored", "variation_render_needs_confirmation",
    "variation_finished", "variation_two_candidates", "variation_rendered_with_checks",
    "variation_candidates_differ", "variation_project_unchanged",
    "candidate_apply_needs_confirmation", "candidate_applied", "key_saved",
    "key_never_shown", "key_removed", "validate_without_key_is_auth",
)


def wav_format(path):
    data = Path(path).read_bytes()
    if data[:4] != b"RIFF" or data[8:12] != b"WAVE":
        raise AssertionError("not a RIFF/WAVE file: {}".format(path))
    offset, fmt, size = 12, None, None
    while offset + 8 <= len(data):
        name, length = struct.unpack_from("<4sI", data, offset)
        if name == b"fmt ":
            fmt = struct.unpack_from("<HHIIHH", data, offset + 8)
        elif name == b"data":
            size = length
        offset += 8 + length + (length & 1)
    if fmt is None or size is None:
        raise AssertionError("WAV lacks fmt or data chunk")
    channels, rate, bits = fmt[1], fmt[2], fmt[5]
    frames = size // (channels * bits // 8)
    return rate, channels, frames / float(rate)


class AssistantIntegrationTests(harness.ScenarioTestCase):
    @classmethod
    def setUpClass(cls):
        scsynth = harness.resolve_executable("SCSYNTH", "scsynth")
        sclang = harness.resolve_executable("SCLANG", "sclang")
        plugin_dir = harness.ensure_plugin_built()
        builtin = harness.builtin_plugin_dir(scsynth)
        work = harness.new_work_dir("gui-integration")
        project = work / "project"
        project.mkdir()
        (project / "main.scd").write_text(ORIGINAL, encoding="utf-8")
        (project / "notes.txt").write_text("Integration fixture notes\n", encoding="utf-8")
        cls.work = work
        cls.scenario_run = harness.run_scenario_file(
            ROOT / "tests" / "mb_gui" / "integration_scenario.scd",
            work, (plugin_dir, builtin, sclang, scsynth), timeout=960,
        )

    def test_scenario_completed_without_failures(self):
        self.assertScenarioCompleted()

    def test_every_workflow_step_ran_and_passed(self):
        self.assertChecks(*REQUIRED)

    def test_rendered_wav_matches_the_requested_settings(self):
        lines = [line for line in self.scenario_run.stdout.splitlines() if "MBTEST INFO wav=" in line]
        self.assertEqual(len(lines), 1, self.scenario_run.stdout[-3000:])
        path = lines[0].split("wav=", 1)[1].strip()
        self.assertGreater(os.path.getsize(path), 1000)
        rate, channels, seconds = wav_format(path)
        self.assertEqual((rate, channels), (48000, 2))
        self.assertAlmostEqual(seconds, 2.0, delta=0.01)
        self.assertTrue(Path(path[:-4] + ".json").is_file())

    def test_no_key_is_written_anywhere(self):
        offenders = []
        for directory, _, files in os.walk(str(self.work)):
            for name in files:
                path = os.path.join(directory, name)
                try:
                    with open(path, "rb") as handle:
                        if SECRET_FRAGMENT.encode() in handle.read():
                            offenders.append(path)
                except OSError:
                    pass
        self.assertEqual(offenders, [])
        self.assertNotIn(SECRET_FRAGMENT, self.scenario_run.stdout)


if __name__ == "__main__":
    unittest.main()
