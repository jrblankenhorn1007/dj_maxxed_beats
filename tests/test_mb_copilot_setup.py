"""Offline tests for Copilot setup paths and runtime configuration."""
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

from mb_providers.harness import ROOT

SETUP_PATH = ROOT / "extension" / "Data" / "copilot" / "setup_copilot.py"


def load_setup():
    if not SETUP_PATH.is_file():
        raise AssertionError("the installed Copilot runtime setup helper is missing")
    directory = str(SETUP_PATH.parent)
    sys.path.insert(0, directory)
    try:
        spec = importlib.util.spec_from_file_location("mb_copilot_setup", SETUP_PATH)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    finally:
        sys.path.remove(directory)


class CopilotSetupTests(unittest.TestCase):
    def setUp(self):
        self.setup = load_setup()
        self.temporary_directory = tempfile.TemporaryDirectory(prefix="copilot-setup-")
        self.addCleanup(self.temporary_directory.cleanup)
        self.root = Path(self.temporary_directory.name)

    def test_platform_settings_and_runtime_directories(self):
        home = self.root / "user"
        appdata = home / "AppData" / "Roaming"
        local_appdata = home / "AppData" / "Local"
        xdg_config = home / "xdg-config"
        xdg_data = home / "xdg-data"

        self.assertEqual(
            self.setup.settings_directory("darwin", home, {}),
            home / "Library" / "Application Support" / "SuperCollider" / "MaxxedBeats")
        self.assertEqual(
            self.setup.settings_directory("win32", home, {"APPDATA": str(appdata)}),
            appdata / "SuperCollider" / "MaxxedBeats")
        self.assertEqual(
            self.setup.settings_directory("linux", home, {"XDG_CONFIG_HOME": str(xdg_config)}),
            xdg_config / "SuperCollider" / "MaxxedBeats")
        self.assertEqual(
            self.setup.runtime_directory("darwin", home, {}),
            home / "Library" / "Application Support" / "MaxxedBeats" / "Copilot")
        self.assertEqual(
            self.setup.runtime_directory("win32", home, {"LOCALAPPDATA": str(local_appdata)}),
            local_appdata / "MaxxedBeats" / "Copilot")
        self.assertEqual(
            self.setup.runtime_directory("linux", home, {"XDG_DATA_HOME": str(xdg_data)}),
            xdg_data / "MaxxedBeats" / "Copilot")

    def test_windows_virtual_environment_uses_windows_python_path(self):
        venv_directory = Path("C:/Users/friend/AppData/Local/MaxxedBeats/Copilot/venv")
        self.assertEqual(
            self.setup.python_in_venv(venv_directory, "win32"),
            venv_directory / "Scripts" / "python.exe")

    def test_mac_and_linux_setup_launchers_are_executable(self):
        if os.name == "nt":
            self.skipTest("Windows setup is launched with the packaged .cmd file")
        for filename in ("setup-copilot.command", "setup-copilot.sh"):
            with self.subTest(filename=filename):
                self.assertTrue(os.access(SETUP_PATH.with_name(filename), os.X_OK))

    def test_cli_setup_uses_official_installer_only_when_missing(self):
        with mock.patch.object(
                self.setup, "resolve_cli",
                side_effect=[self.setup.BackendError("config", "missing"), "/native/copilot"]) as resolve, \
                mock.patch.object(self.setup.subprocess, "run") as run:
            result = self.setup.resolve_cli_for_setup(install_cli=True, platform_name="darwin")
        self.assertEqual(result, "/native/copilot")
        resolve.assert_has_calls([mock.call({}), mock.call({})])
        run.assert_called_once_with(
            ["bash", "-c", "curl -fsSL https://gh.io/copilot-install | bash"],
            check=True, timeout=300)

    def test_setup_preserves_cli_shim_path_for_package_updates(self):
        target = self.root / "packages" / "copilot-v1" / "copilot.exe"
        shim = self.root / "WinGet" / "Links" / "copilot.exe"
        target.parent.mkdir(parents=True)
        shim.parent.mkdir(parents=True)
        target.touch()
        shim.symlink_to(target)

        self.assertEqual(
            self.setup.resolve_cli_for_setup(str(shim), platform_name="win32"),
            str(shim.absolute()))

    def test_setup_installs_pinned_sdk_and_saves_runtime_paths(self):
        settings_directory = self.root / "settings"
        runtime_directory = self.root / "runtime"
        cli_path = str((self.root / "copilot").resolve())
        python_path = self.setup.python_in_venv(runtime_directory / "venv")
        builder = mock.Mock()

        def create_environment(directory):
            python_path.parent.mkdir(parents=True)
            python_path.touch()

        builder.return_value.create.side_effect = create_environment
        with mock.patch.object(self.setup, "resolve_cli", return_value=cli_path) as resolve_cli, \
                mock.patch.object(self.setup.venv, "EnvBuilder", return_value=builder.return_value) as env_builder, \
                mock.patch.object(self.setup.subprocess, "run") as run:
            configured = self.setup.setup_runtime(
                python_version=(3, 13),
                settings_dir=settings_directory,
                runtime_dir=runtime_directory)

        config_path = settings_directory / "copilot-runtime.json"
        config = json.loads(config_path.read_text(encoding="utf-8"))
        self.assertEqual(configured, config)
        self.assertEqual(config["pythonPath"], str(python_path.absolute()))
        self.assertEqual(config["cliPath"], cli_path)
        self.assertEqual(set(config), {"pythonPath", "cliPath"})
        env_builder.assert_called_once_with(with_pip=True)
        builder.return_value.create.assert_called_once_with(runtime_directory / "venv")
        resolve_cli.assert_called_once_with({})
        calls = [call.args[0] for call in run.call_args_list]
        self.assertIn([
            str(python_path), "-m", "pip", "install",
            "--disable-pip-version-check", "-r",
            str(SETUP_PATH.with_name("requirements.txt"))], calls)
        self.assertIn([cli_path, "--version"], calls)
        self.assertTrue(all(call.kwargs.get("shell") is not True for call in run.call_args_list))

    def test_setup_refuses_python_below_311_before_installing(self):
        with mock.patch.object(self.setup, "resolve_cli",
                               side_effect=AssertionError("CLI lookup must not run")):
            with self.assertRaisesRegex(self.setup.SetupError, "3.11"):
                self.setup.setup_runtime(
                    python_version=(3, 10),
                    settings_dir=self.root / "settings",
                    runtime_dir=self.root / "runtime")
        self.assertFalse((self.root / "runtime").exists())

    def test_failed_dependency_install_does_not_save_runtime_config(self):
        runtime_directory = self.root / "runtime"
        python_path = self.setup.python_in_venv(runtime_directory / "venv")
        builder = mock.Mock()

        def create_environment(directory):
            python_path.parent.mkdir(parents=True)
            python_path.touch()

        builder.return_value.create.side_effect = create_environment
        failure = self.setup.subprocess.CalledProcessError(1, ["pip"])
        with mock.patch.object(self.setup, "resolve_cli", return_value=str(self.root / "copilot")), \
                mock.patch.object(self.setup.venv, "EnvBuilder", return_value=builder.return_value), \
                mock.patch.object(self.setup.subprocess, "run", side_effect=[
                    self.setup.subprocess.CompletedProcess(["copilot", "--version"], 0),
                    failure]):
            with self.assertRaises(self.setup.SetupError):
                self.setup.setup_runtime(
                    python_version=(3, 13),
                    settings_dir=self.root / "settings",
                    runtime_dir=runtime_directory)
        self.assertFalse((self.root / "settings" / "copilot-runtime.json").exists())


if __name__ == "__main__":
    unittest.main()
