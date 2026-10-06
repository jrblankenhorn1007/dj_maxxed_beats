import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CLASS_PATH = ROOT / "plugin" / "ChaosOsc" / "Classes" / "ChaosOsc.sc"
HELP_PATH = (
    ROOT
    / "plugin"
    / "ChaosOsc"
    / "HelpSource"
    / "Classes"
    / "ChaosOsc.schelp"
)


def constructor_pattern(method, rate):
    return re.compile(
        r"\*" + method + r"\s*\{\s*\|\s*"
        r"chaosAmount\s*=\s*3\.9\s*,\s*"
        r"seed\s*=\s*0\.5\s*,\s*"
        r"freq\s*=\s*inf\s*,\s*"
        r"mul\s*=\s*1\.0\s*,\s*"
        r"add\s*=\s*0\.0\s*\|"
        r"\s*\^this\.multiNew\(\s*'" + rate + r"'\s*,\s*chaosAmount\s*,"
        r"\s*seed\s*,\s*freq\s*\)\.madd\(\s*mul\s*,\s*add\s*\)\s*\}",
        re.DOTALL,
    )


class ChaosOscLanguageContractTests(unittest.TestCase):
    def test_audio_constructor_uses_documented_defaults_and_controls(self):
        source = CLASS_PATH.read_text(encoding="utf-8")
        self.assertRegex(source, r"ChaosOsc\s*:\s*UGen\s*\{")
        self.assertRegex(source, constructor_pattern("ar", "audio"))

    def test_control_constructor_mirrors_the_audio_constructor(self):
        source = CLASS_PATH.read_text(encoding="utf-8")
        self.assertRegex(source, constructor_pattern("kr", "control"))

    def test_help_documents_controls_and_constructor(self):
        help_source = HELP_PATH.read_text(encoding="utf-8")
        for expected in (
            "ChaosOsc.ar(chaosAmount, seed, freq, mul, add)",
            "ChaosOsc.kr(chaosAmount, seed, freq, mul, add)",
            "METHOD:: ar, kr",
            "ARGUMENT:: chaosAmount",
            "ARGUMENT:: seed",
            "ARGUMENT:: freq",
            "ARGUMENT:: mul",
            "ARGUMENT:: add",
            "clamped by the plugin to the range 3.57 to 3.999",
            "Audio-rate inputs are read per sample",
            "control-rate inputs are read once per block",
            "captured when the Synth is created",
            "Defaults to code::inf::",
            "advances once per output sample",
            "linearly interpolated between successive map states",
            "holds (freezes) its current value",
            "NaN behaves like the default",
            "bit-identical",
            "range -1 to 1",
        ):
            with self.subTest(expected=expected):
                self.assertIn(expected, help_source)

    def test_help_documents_the_dc_offset_and_leakdc_idiom(self):
        help_source = HELP_PATH.read_text(encoding="utf-8")
        for expected in (
            "emphasis::not:: zero-mean",
            "+0.19",
            "+0.34",
            "-0.32 to 0.79",
            "LeakDC.ar(ChaosOsc.ar(",
        ):
            with self.subTest(expected=expected):
                self.assertIn(expected, help_source)

    def test_help_examples_cover_audio_noise_and_slow_modulation(self):
        help_source = HELP_PATH.read_text(encoding="utf-8")
        examples = help_source.split("EXAMPLES::", 1)
        self.assertEqual(len(examples), 2, "help has no EXAMPLES section")
        self.assertIn("LeakDC.ar(ChaosOsc.ar(", examples[1])
        self.assertRegex(examples[1], r"ChaosOsc\.kr\([^)]*,[^)]*,\s*\d")


if __name__ == "__main__":
    unittest.main()
