"""Tests for scripts/install_maxxedbeats.py (Quark + ChaosOsc installer).

The ChaosOsc CMake build is replaced by a fake that writes a marked plugin
folder, so these tests never compile; the CI workflow
(.github/workflows/assistant-tests.yml) runs the real installer.
"""

import contextlib
import io
import os
from pathlib import Path
import shutil
import subprocess
import sys
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
BUILD_DIR = ROOT / "tests" / ".build" / "mb-install"
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(ROOT / "tests"))

import install_chaososc  # noqa: E402
import install_maxxedbeats as installer  # noqa: E402


class FakeChaosOsc:
    """Stands in for install_chaososc.install/uninstall without CMake."""

    def __init__(self, fail=False):
        self.fail = fail
        self.installs = []
        self.uninstalls = []

    def install(self, args):
        self.installs.append(args)
        print("ChaosOsc installer{}".format(" (dry run)" if args.dry_run else ""))
        if self.fail:
            raise install_chaososc.InstallerError("ChaosOsc build failed (fake)")
        if args.dry_run:
            return 0
        target = Path(args.extensions_dir) / "ChaosOsc"
        if target.exists():
            shutil.rmtree(str(target))
        (target / "Classes").mkdir(parents=True)
        (target / install_chaososc.MARKER_NAME).write_text("marker", encoding="utf-8")
        print(install_chaososc.NEXT_STEPS_INSTALL)
        return 0

    def uninstall(self, args):
        self.uninstalls.append(args)
        target = Path(args.extensions_dir) / "ChaosOsc"
        if target.exists() and not args.dry_run:
            shutil.rmtree(str(target))
        print(install_chaososc.NEXT_STEPS_UNINSTALL)
        return 0


class InstallerTestCase(unittest.TestCase):
    def setUp(self):
        self.extensions = BUILD_DIR / self.id().split(".")[-1] / "Extensions"
        if self.extensions.parent.exists():
            shutil.rmtree(str(self.extensions.parent))
        self.extensions.mkdir(parents=True)
        self.fake = FakeChaosOsc()

    def run_installer(self, *arguments, fake=None):
        fake = fake or self.fake
        out, err = io.StringIO(), io.StringIO()
        with mock.patch.object(installer.install_chaososc, "install", fake.install), \
                mock.patch.object(installer.install_chaososc, "uninstall", fake.uninstall), \
                contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = installer.main(["--extensions-dir", str(self.extensions)] + list(arguments))
        return code, out.getvalue(), err.getvalue()

    @property
    def quark(self):
        return self.extensions / "MaxxedBeats"


class InstallTests(InstallerTestCase):
    def test_installs_quark_agent_instructions_and_plugin_together(self):
        code, out, err = self.run_installer("--build-dir", "custom-build")
        self.assertEqual(code, 0, err)
        for relative in (
            "MaxxedBeats.quark",
            "Classes/MaxxedBeats.sc",
            "Classes/GUI/MBGuiWindow.sc",
            "Classes/Core/MBError.sc",
            "HelpSource/Classes/MaxxedBeats.schelp",
            "agent/WORKFLOW.md",
            installer.MARKER_NAME,
        ):
            with self.subTest(path=relative):
                self.assertTrue((self.quark / relative).is_file(), relative)
        self.assertTrue((self.extensions / "ChaosOsc" / install_chaososc.MARKER_NAME).is_file())
        plugin_args = self.fake.installs[0]
        self.assertEqual(Path(plugin_args.extensions_dir), self.extensions)
        self.assertTrue(plugin_args.build_dir.endswith("custom-build"))
        self.assertFalse(plugin_args.dry_run)
        self.assertEqual(out.count("Next steps:"), 1, out)
        self.assertIn("Recompile", out)
        self.assertIn("s.reboot", out)
        self.assertIn("MaxxedBeats.gui", out)
        self.assertFalse(list(self.extensions.glob(".MaxxedBeats*")), "staging folder left behind")

    def test_reinstall_replaces_only_a_marked_install(self):
        self.assertEqual(self.run_installer()[0], 0)
        stray = self.quark / "Classes" / "Stale.sc"
        stray.write_text("Stale {}", encoding="utf-8")
        code, _, err = self.run_installer()
        self.assertEqual(code, 0, err)
        self.assertFalse(stray.exists())

    def test_refuses_unmarked_quark_folder_before_building_anything(self):
        (self.quark / "Classes").mkdir(parents=True)
        mine = self.quark / "Classes" / "Mine.sc"
        mine.write_text("Mine {}", encoding="utf-8")
        code, _, err = self.run_installer()
        self.assertEqual(code, 1)
        self.assertIn("refusing", err)
        self.assertIn("--force", err)
        self.assertTrue(mine.exists())
        self.assertEqual(self.fake.installs, [])

    def test_refuses_unmarked_chaososc_folder_before_installing_the_quark(self):
        (self.extensions / "ChaosOsc").mkdir()
        code, _, err = self.run_installer()
        self.assertEqual(code, 1)
        self.assertIn("ChaosOsc", err)
        self.assertFalse(self.quark.exists())
        self.assertEqual(self.fake.installs, [])

    def test_force_replaces_unmarked_folders(self):
        (self.quark / "Classes").mkdir(parents=True)
        (self.quark / "Classes" / "Mine.sc").write_text("Mine {}", encoding="utf-8")
        code, _, err = self.run_installer("--force")
        self.assertEqual(code, 0, err)
        self.assertTrue((self.quark / installer.MARKER_NAME).is_file())
        self.assertFalse((self.quark / "Classes" / "Mine.sc").exists())
        self.assertTrue(self.fake.installs[0].force)

    def test_plugin_failure_leaves_the_quark_uninstalled(self):
        code, _, err = self.run_installer(fake=FakeChaosOsc(fail=True))
        self.assertEqual(code, 1)
        self.assertIn("ChaosOsc build failed", err)
        self.assertFalse(self.quark.exists())

    def test_dry_run_changes_nothing(self):
        code, out, err = self.run_installer("--dry-run")
        self.assertEqual(code, 0, err)
        self.assertEqual(list(self.extensions.iterdir()), [])
        self.assertTrue(self.fake.installs[0].dry_run)
        self.assertIn("Dry run", out)
        self.assertIn(str(self.quark), out)

    def test_warns_about_duplicate_copies_and_include_paths(self):
        duplicate = self.extensions / "old-checkout" / "Classes"
        duplicate.mkdir(parents=True)
        (duplicate / "MaxxedBeats.sc").write_text("MaxxedBeats {}", encoding="utf-8")
        (self.extensions.parent / "sclang_conf.yaml").write_text(
            "includePaths:\n    -   {}\n".format(ROOT / "extension"), encoding="utf-8"
        )
        code, out, err = self.run_installer()
        self.assertEqual(code, 0, err)
        self.assertIn("WARNING", out)
        self.assertIn("old-checkout", out)
        self.assertIn("sclang_conf.yaml", out)


class UninstallTests(InstallerTestCase):
    def test_uninstall_removes_both_marked_components(self):
        self.assertEqual(self.run_installer()[0], 0)
        code, out, err = self.run_installer("--uninstall")
        self.assertEqual(code, 0, err)
        self.assertFalse(self.quark.exists())
        self.assertFalse((self.extensions / "ChaosOsc").exists())
        self.assertEqual(len(self.fake.uninstalls), 1)
        self.assertEqual(out.count("Next steps:"), 1, out)

    def test_uninstall_refuses_unmarked_quark_and_keeps_everything(self):
        self.assertEqual(self.run_installer()[0], 0)
        (self.quark / installer.MARKER_NAME).unlink()
        code, _, err = self.run_installer("--uninstall")
        self.assertEqual(code, 1)
        self.assertIn("refusing", err)
        self.assertTrue(self.quark.exists())
        self.assertTrue((self.extensions / "ChaosOsc").exists())
        self.assertEqual(self.fake.uninstalls, [])

    def test_uninstall_dry_run_removes_nothing(self):
        self.assertEqual(self.run_installer()[0], 0)
        code, out, err = self.run_installer("--uninstall", "--dry-run")
        self.assertEqual(code, 0, err)
        self.assertTrue(self.quark.exists())
        self.assertIn("would remove", out)
        self.assertTrue(self.fake.uninstalls[0].dry_run)

    def test_uninstall_with_nothing_installed_is_a_no_op(self):
        code, out, err = self.run_installer("--uninstall")
        self.assertEqual(code, 0, err)
        self.assertIn("Nothing to uninstall", out)


class PlatformAndCliTests(unittest.TestCase):
    def test_default_extensions_dir_matches_supercollider_per_platform(self):
        self.assertEqual(
            installer.default_extensions_dir("darwin", {"HOME": "/Users/a"}),
            "/Users/a/Library/Application Support/SuperCollider/Extensions",
        )
        self.assertEqual(
            installer.default_extensions_dir("linux", {"HOME": "/home/a"}),
            "/home/a/.local/share/SuperCollider/Extensions",
        )
        self.assertEqual(
            installer.default_extensions_dir("win32", {"LOCALAPPDATA": "C:\\Users\\a\\AppData\\Local"}),
            "C:\\Users\\a\\AppData\\Local\\SuperCollider\\Extensions",
        )

    def test_cli_help_and_empty_uninstall_run_without_cmake(self):
        extensions = BUILD_DIR / "cli" / "Extensions"
        extensions.mkdir(parents=True, exist_ok=True)
        for arguments in (["--help"], ["--uninstall", "--dry-run", "--extensions-dir", str(extensions)]):
            with self.subTest(arguments=arguments):
                result = subprocess.run(
                    [sys.executable, str(SCRIPTS / "install_maxxedbeats.py")] + arguments,
                    cwd=str(ROOT), capture_output=True, text=True, timeout=60,
                )
                self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("--uninstall", result.stdout + subprocess.run(
            [sys.executable, str(SCRIPTS / "install_maxxedbeats.py"), "--help"],
            cwd=str(ROOT), capture_output=True, text=True, timeout=60).stdout)

    def test_installed_quark_compiles_from_its_installed_location(self):
        from test_mb_gui import run_sclang_script, parse_results

        extensions = BUILD_DIR / "compile" / "Extensions"
        if extensions.parent.exists():
            shutil.rmtree(str(extensions.parent))
        extensions.mkdir(parents=True)
        installer.install_quark(str(extensions), force=False)
        script = extensions.parent / "check.scd"
        script.write_text(
            "(\n"
            '("MBTEST " ++ (if(MaxxedBeats.respondsTo(\\gui) and: { MBGuiWindow.notNil }) '
            '{ "PASS" } { "FAIL" }) ++ " installed/compiles").postln;\n'
            '"MBTEST DONE passes=1 failures=0".postln;\n'
            "0.exit;\n"
            ")\n",
            encoding="utf-8",
        )
        output = run_sclang_script("installed-compile", script, [extensions / "MaxxedBeats"])
        passes, failures, done = parse_results(output)
        self.assertEqual(failures, [], output[-2000:])
        self.assertEqual(len(passes), 1, output[-2000:])
        self.assertNotIn("duplicate", output.lower())


if __name__ == "__main__":
    unittest.main()
