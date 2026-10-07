"""MaxxedBeats-Windows-x64.zip: layout of the no-developer-tools Windows
package (scripts/package_windows.py) and the behaviour of its marker-protected
install.ps1 / uninstall.ps1, run with PowerShell into a temporary Extensions
folder (Windows PowerShell on Windows, pwsh elsewhere)."""

import os
from pathlib import Path
import shutil
import subprocess
import sys
import unittest
import zipfile
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import package_windows  # noqa: E402

WORK = ROOT / "tests" / ".build" / "mb-package-windows"
WINDOWS = ROOT / "scripts" / "windows"


def fake_pe_x64():
    header = bytearray(0x200)
    header[0:2] = b"MZ"
    header[0x3C:0x40] = (0x80).to_bytes(4, "little")
    header[0x80:0x84] = b"PE\0\0"
    header[0x84:0x86] = (0x8664).to_bytes(2, "little")
    return bytes(header)


def powershell():
    for candidate in (os.environ.get("MB_PWSH"), shutil.which("powershell"), shutil.which("pwsh")):
        if candidate and Path(candidate).is_file():
            return candidate
    return None


def make_chaososc(folder, binary=None):
    if folder.exists():
        shutil.rmtree(str(folder))
    (folder / "Classes").mkdir(parents=True)
    shutil.copy2(str(ROOT / "plugin" / "ChaosOsc" / "Classes" / "ChaosOsc.sc"), str(folder / "Classes"))
    (folder / "ChaosOsc.scx").write_bytes(binary if binary is not None else fake_pe_x64())
    return folder


class PackageLayoutTests(unittest.TestCase):
    def test_scide_launcher_opens_assistant_without_typing_code(self):
        launcher = ROOT / "extension" / "LaunchMaxxedBeats.scd"
        self.assertEqual(launcher.read_text(encoding="utf-8"), "MaxxedBeats.gui;\n")

    def test_zip_holds_quark_agent_plugin_and_scripts(self):
        chaos = make_chaososc(WORK / "stage" / "ChaosOsc")
        package, archive = package_windows.assemble(chaos, WORK / "out")
        self.assertEqual(archive.name, "MaxxedBeats-Windows-x64.zip")
        with zipfile.ZipFile(str(archive)) as handle:
            names = set(handle.namelist())
        prefix = "MaxxedBeats-Windows-x64/"
        for required in package_windows.REQUIRED:
            self.assertIn(prefix + required, names)
        for agent in sorted((ROOT / "agent").glob("*.md")):
            self.assertIn(prefix + "MaxxedBeats/agent/" + agent.name, names)
        self.assertIn(prefix + "MaxxedBeats/Classes/Workflow/MBRenderer.sc", names)
        self.assertFalse([n for n in names if n.endswith("-install-marker")], names)
        self.assertFalse([n for n in names if "/.build/" in n or n.endswith(".pyc")])
        self.assertTrue(all(n.startswith(prefix) for n in names))

    def test_zip_contains_one_click_windows_and_cross_platform_copilot_setup(self):
        chaos = make_chaososc(WORK / "stage-copilot-setup" / "ChaosOsc")
        _, archive = package_windows.assemble(chaos, WORK / "out-copilot-setup")
        with zipfile.ZipFile(str(archive)) as handle:
            names = set(handle.namelist())
        prefix = "MaxxedBeats-Windows-x64/"
        required = (
            "Install-MaxxedBeats.cmd",
            "Setup-Copilot.cmd",
            "Uninstall-MaxxedBeats.cmd",
            "setup-copilot.ps1",
            "MaxxedBeats/Data/copilot/setup_copilot.py",
            "MaxxedBeats/Data/copilot/setup-copilot.command",
            "MaxxedBeats/Data/copilot/setup-copilot.sh",
        )
        for name in required:
            self.assertIn(prefix + name, names)

    def test_package_requires_the_copilot_runtime_files(self):
        chaos = make_chaososc(WORK / "stage-no-copilot" / "ChaosOsc")
        quark = WORK / "source-no-copilot"
        if quark.exists():
            shutil.rmtree(str(quark))
        shutil.copytree(package_windows.QUARK_SOURCE, quark)
        shutil.rmtree(str(quark / "Data" / "copilot"))
        with mock.patch.object(package_windows, "QUARK_SOURCE", quark):
            with self.assertRaisesRegex(package_windows.PackageError, "Data/copilot"):
                package_windows.assemble(chaos, WORK / "out-no-copilot")

    def test_rejects_a_non_windows_plugin_binary(self):
        chaos = make_chaososc(WORK / "stage-bad" / "ChaosOsc", binary=b"\x7fELF not a dll")
        with self.assertRaises(package_windows.PackageError):
            package_windows.assemble(chaos, WORK / "out-bad")
        self.assertFalse(package_windows.is_pe_x64(chaos / "ChaosOsc.scx"))
        self.assertTrue(package_windows.is_pe_x64(make_chaososc(WORK / "stage-ok" / "ChaosOsc") / "ChaosOsc.scx"))

    def test_scripts_default_to_supercollider_user_extensions_and_print_next_steps(self):
        install = (WINDOWS / "install.ps1").read_text(encoding="utf-8")
        uninstall = (WINDOWS / "uninstall.ps1").read_text(encoding="utf-8")
        for text in (install, uninstall):
            self.assertIn("LocalApplicationData", text)
            self.assertIn("'SuperCollider'", text)
            self.assertIn("'Extensions'", text)
            self.assertIn(".maxxedbeats-install-marker", text)
            self.assertIn(".chaososc-install-marker", text)
            self.assertIn("Recompile Class Library", text)
        self.assertIn("s.reboot", uninstall)
        self.assertIn("LaunchMaxxedBeats.scd", install)
        self.assertIn("Ctrl+Enter", install)
        launcher = (WINDOWS / "Install-MaxxedBeats.cmd").read_text(encoding="utf-8")
        self.assertIn("install.ps1", launcher)
        self.assertIn("setup-copilot.ps1", launcher)
        setup_launcher = (WINDOWS / "Setup-Copilot.cmd").read_text(encoding="utf-8")
        self.assertIn("setup-copilot.ps1", setup_launcher)
        uninstall_launcher = (WINDOWS / "Uninstall-MaxxedBeats.cmd").read_text(encoding="utf-8")
        self.assertIn("uninstall.ps1", uninstall_launcher)
        readme = (WINDOWS / "README.txt").read_text(encoding="utf-8")
        self.assertIn("double-click Install-MaxxedBeats.cmd", readme)
        self.assertIn("Setup-Copilot.cmd", readme)
        self.assertIn("Uninstall-MaxxedBeats.cmd", readme)


@unittest.skipUnless(powershell(), "PowerShell (Windows PowerShell or pwsh) is required")
class PackageScriptTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        chaos = make_chaososc(WORK / "stage-scripts" / "ChaosOsc")
        cls.package, _ = package_windows.assemble(chaos, WORK / "out-scripts")

    def run_script(self, name, extensions, *arguments):
        return subprocess.run(
            [powershell(), "-NoLogo", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
             "-File", str(self.package / name), "-ExtensionsDir", str(extensions), *arguments],
            capture_output=True, text=True, timeout=180)

    def fresh(self, name):
        folder = WORK / "ext" / name / "Extensions with space"
        if folder.parent.exists():
            shutil.rmtree(str(folder.parent))
        return folder

    def test_install_reinstall_and_uninstall(self):
        extensions = self.fresh("roundtrip")
        result = self.run_script("install.ps1", extensions)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertTrue((extensions / "MaxxedBeats" / ".maxxedbeats-install-marker").is_file())
        self.assertTrue((extensions / "MaxxedBeats" / "agent" / "SAFETY.md").is_file())
        self.assertTrue((extensions / "MaxxedBeats" / "Data" / "windows" / "MaxxedBeatsLaunch.ps1").is_file())
        self.assertTrue((extensions / "ChaosOsc" / ".chaososc-install-marker").is_file())
        self.assertTrue((extensions / "ChaosOsc" / "ChaosOsc.scx").is_file())
        self.assertIn("Recompile Class Library", result.stdout)
        self.assertIn("LaunchMaxxedBeats.scd", result.stdout)
        self.assertIn("Ctrl+Enter", result.stdout)
        self.assertEqual([p.name for p in extensions.iterdir() if p.name.startswith(".")], [])
        (extensions / "MaxxedBeats" / "stale.txt").write_text("old")
        result = self.run_script("install.ps1", extensions)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertFalse((extensions / "MaxxedBeats" / "stale.txt").exists())
        result = self.run_script("uninstall.ps1", extensions)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertFalse((extensions / "MaxxedBeats").exists())
        self.assertFalse((extensions / "ChaosOsc").exists())
        self.assertIn("Recompile Class Library", result.stdout)

    def test_unmarked_folders_are_never_replaced_or_removed(self):
        extensions = self.fresh("unmarked")
        (extensions / "ChaosOsc").mkdir(parents=True)
        (extensions / "ChaosOsc" / "mine.txt").write_text("user data")
        result = self.run_script("install.ps1", extensions)
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("not installed by MaxxedBeats", result.stderr)
        self.assertFalse((extensions / "MaxxedBeats").exists())
        self.assertEqual((extensions / "ChaosOsc" / "mine.txt").read_text(), "user data")
        result = self.run_script("uninstall.ps1", extensions)
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertTrue((extensions / "ChaosOsc" / "mine.txt").is_file())

    def test_copilot_setup_uses_installed_extension_paths_without_system_changes(self):
        extensions = self.fresh("copilot-setup")
        installed = self.run_script("install.ps1", extensions)
        self.assertEqual(installed.returncode, 0, installed.stdout + installed.stderr)
        cli = r"C:\Program Files\GitHub Copilot\copilot.exe"
        result = self.run_script(
            "setup-copilot.ps1", extensions,
            "-PythonExecutable", sys.executable,
            "-CopilotCliPath", cli,
            "-DryRun")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn(str(extensions / "MaxxedBeats" / "Data" / "copilot" /
                          "setup_copilot.py"), result.stdout)
        self.assertIn(cli, result.stdout)


if __name__ == "__main__":
    unittest.main()
