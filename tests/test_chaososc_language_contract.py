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


class ChaosOscLanguageContractTests(unittest.TestCase):
    def test_audio_constructor_uses_documented_defaults_and_controls(self):
        source = CLASS_PATH.read_text(encoding="utf-8")
        self.assertRegex(source, r"ChaosOsc\s*:\s*UGen\s*\{")
        self.assertRegex(
            source,
            re.compile(
                r"\*ar\s*\{\s*\|chaosAmount\s*=\s*3\.9,\s*seed\s*=\s*0\.5\|"
                r"\s*\^this\.multiNew\('audio',\s*chaosAmount,\s*seed\)\s*\}",
                re.DOTALL,
            ),
        )

    def test_help_documents_controls_and_constructor(self):
        help_source = HELP_PATH.read_text(encoding="utf-8")
        for expected in (
            "ChaosOsc.ar(chaosAmount, seed)",
            "chaosAmount",
            "Audio-rate inputs are read per sample",
            "control-rate inputs are broadcast across each audio block",
            "seed",
            "captured when the Synth is created",
        ):
            with self.subTest(expected=expected):
                self.assertIn(expected, help_source)


if __name__ == "__main__":
    unittest.main()
