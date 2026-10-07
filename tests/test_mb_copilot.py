"""Offline tests for the optional Copilot subscription backend; never generate
against a real account or change the CLI's authentication/configuration."""
import asyncio
import importlib.util
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest import mock

from mb_providers.harness import BUILD_DIR, ROOT, run_sclang, sc_string

BRIDGE = ROOT / "extension" / "Data" / "copilot" / "bridge.py"


def load_bridge():
    spec = importlib.util.spec_from_file_location("mb_copilot_bridge", BRIDGE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class FakeSession:
    session_id = "fake-session"

    def __init__(self, client):
        self.client = client
        self.rpc = types.SimpleNamespace(
            model=types.SimpleNamespace(get_current=self.current),
            tools=types.SimpleNamespace(get_current_metadata=self.metadata))

    async def metadata(self):
        return types.SimpleNamespace(tools=self.client.tools)

    async def current(self):
        return types.SimpleNamespace(model_id=self.client.current_model)

    async def send_and_wait(self, prompt, timeout):
        self.client.prompts.append(prompt)
        if self.client.delay:
            await asyncio.sleep(self.client.delay)
        if self.client.error:
            raise RuntimeError(self.client.error)
        return types.SimpleNamespace(data=types.SimpleNamespace(content="proposal only"))

    async def abort(self):
        self.client.aborted = True

    async def disconnect(self):
        self.client.disconnected = True


class FakeClient:
    def __init__(self, current_model="test-model", authenticated=True, delay=0, error=None,
                 tools=None):
        self.current_model = current_model
        self.authenticated = authenticated
        self.delay = delay
        self.error = error
        self.tools = tools or []
        self.prompts = []
        self.options = None
        self.aborted = self.stopped = self.disconnected = False

    async def start(self):
        pass

    async def stop(self):
        self.stopped = True

    async def get_auth_status(self):
        return types.SimpleNamespace(isAuthenticated=self.authenticated)

    async def list_models(self):
        return [types.SimpleNamespace(id="test-model", name="Live model", policy=None),
                types.SimpleNamespace(id="blocked-model", name="Disabled",
                                      policy=types.SimpleNamespace(state="disabled"))]

    async def create_session(self, **options):
        self.options = options
        return FakeSession(self)


class FakeLoginProcess:
    def __init__(self, code=0, delay=0):
        self.code, self.delay = code, delay
        self.returncode = None
        self.terminated = self.killed = False

    async def wait(self):
        if self.returncode is None:
            await asyncio.sleep(self.delay)
            self.returncode = self.code
        return self.returncode

    def terminate(self):
        self.terminated = True
        self.returncode = -15

    def kill(self):
        self.killed = True
        self.returncode = -9


class CopilotBridgeTests(unittest.TestCase):
    def setUp(self):
        self.bridge = load_bridge()
        BUILD_DIR.mkdir(parents=True, exist_ok=True)
        self.directory = tempfile.TemporaryDirectory(prefix="copilot-", dir=str(BUILD_DIR))
        self.addCleanup(self.directory.cleanup)
        self.directory = Path(self.directory.name)

    def test_resolve_cli_finds_per_user_native_install_outside_path(self):
        home = self.directory / "home"
        platform_name = (
            "darwin" if sys.platform == "darwin"
            else "win32" if sys.platform == "win32"
            else "linux"
        )
        executable_name = "copilot.exe" if platform_name == "win32" else "copilot"
        cli = (home / ".local" / "copilot-cli" / "lib" / "node_modules" /
               "@github" / "copilot" / "node_modules" / "@github" /
               ("copilot-" + platform_name + "-test") / executable_name)
        cli.parent.mkdir(parents=True)
        cli.write_bytes(b"native Copilot CLI fixture")
        with mock.patch.object(self.bridge.Path, "home", return_value=home), \
                mock.patch.object(self.bridge.shutil, "which", return_value=None):
            self.assertEqual(self.bridge.resolve_cli({}), str(cli.resolve()))

    def test_resolve_cli_finds_windows_package_install_outside_path(self):
        home = self.directory / "home"
        appdata = home / "AppData" / "Roaming"
        cli = (appdata / "npm" / "node_modules" / "@github" / "copilot" /
               "node_modules" / "@github" / "copilot-win32-x64" / "copilot.exe")
        cli.parent.mkdir(parents=True)
        cli.write_bytes(b"native Copilot CLI fixture")
        with mock.patch.object(self.bridge.sys, "platform", "win32"), \
                mock.patch.object(self.bridge.Path, "home", return_value=home), \
                mock.patch.object(self.bridge.shutil, "which", return_value=None), \
                mock.patch.dict(self.bridge.os.environ, {"APPDATA": str(appdata)}):
            self.assertEqual(self.bridge.resolve_cli({}), str(cli.resolve()))

    def test_old_python_error_names_the_platform_setup_launcher(self):
        cases = (
            ("darwin", "setup-copilot.command", "Double-click"),
            ("linux", "setup-copilot.sh", "terminal"),
            ("win32", "Setup-Copilot.cmd", "Double-click"),
        )
        for platform_name, launcher, action in cases:
            with self.subTest(platform=platform_name), \
                    mock.patch.object(self.bridge.sys, "version_info", (3, 10)), \
                    mock.patch.object(self.bridge.sys, "platform", platform_name):
                with self.assertRaises(self.bridge.BackendError) as caught:
                    self.bridge.sdk_client({}, self.directory)
            self.assertEqual(caught.exception.kind, "config")
            detail = caught.exception.detail.lower()
            self.assertIn("python 3.11+", detail)
            self.assertIn("git authorization", detail)
            self.assertIn("api key", detail)
            self.assertIn(launcher.lower(), detail)
            self.assertIn(action.lower(), detail)

    def test_missing_sdk_error_names_the_platform_setup_launcher(self):
        launchers = {
            "darwin": "setup-copilot.command",
            "linux": "setup-copilot.sh",
            "win32": "Setup-Copilot.cmd",
        }
        for platform_name, launcher in launchers.items():
            with self.subTest(platform=platform_name), \
                    mock.patch.object(self.bridge.sys, "version_info", (3, 11)), \
                    mock.patch.object(self.bridge.sys, "platform", platform_name), \
                    mock.patch("importlib.metadata.version", return_value="1.0.16"), \
                    mock.patch.dict("sys.modules", {"copilot": None}):
                with self.assertRaises(self.bridge.BackendError) as caught:
                    self.bridge.sdk_client({}, self.directory)
            self.assertEqual(caught.exception.kind, "config")
            self.assertIn(launcher.lower(), caught.exception.detail.lower())

    def operation(self, client, action="complete", model="test-model", timeout=1):
        spec = {"action": action, "timeout": timeout, "request": {
            "model": model, "system": "Approved system only",
            "messages": [{"role": "user", "content": "Approved context"},
                         {"role": "assistant", "content": "Earlier answer"}],
            "maxOutputTokens": 100, "temperature": None}}
        return asyncio.run(self.bridge.run_operation(spec, self.directory, lambda: client))

    def test_dynamic_models_and_cli_authentication(self):
        client = FakeClient()
        models = self.operation(client, "models")
        self.assertEqual([m["id"] for m in models], ["test-model", "blocked-model"])
        self.assertEqual(models[0]["displayName"], "Live model")
        self.assertEqual([m["usable"] for m in models], [True, False])
        self.assertTrue(client.stopped)
        self.assertEqual(self.operation(FakeClient(), "auth"), {"authenticated": True})
        self.assertEqual(self.operation(FakeClient(authenticated=False), "auth"),
                         {"authenticated": False})

    def test_explicit_browser_login_requires_no_sdk_or_token_handling(self):
        process = FakeLoginProcess()
        launch = mock.AsyncMock(return_value=process)
        with mock.patch.object(self.bridge, "resolve_cli", return_value="native-copilot"), \
                mock.patch.object(self.bridge.asyncio, "create_subprocess_exec", launch), \
                mock.patch.dict("os.environ", {"GH_TOKEN": "fake-private-token",
                                              "OPENAI_API_KEY": "fake-openai-key"}):
            result = self.operation(mock.Mock(side_effect=AssertionError("SDK must not be used")),
                                    "login")
        self.assertEqual(result, {"authenticated": True})
        self.assertEqual(launch.call_args.args, ("native-copilot", "login", "--web-flow"))
        self.assertEqual(launch.call_args.kwargs["stdin"], self.bridge.subprocess.DEVNULL)
        self.assertEqual(launch.call_args.kwargs["stdout"], self.bridge.subprocess.DEVNULL)
        self.assertEqual(launch.call_args.kwargs["stderr"], self.bridge.subprocess.DEVNULL)
        self.assertNotIn("GH_TOKEN", launch.call_args.kwargs["env"])
        self.assertNotIn("OPENAI_API_KEY", launch.call_args.kwargs["env"])

    def test_browser_login_timeout_and_cancellation_stop_cli(self):
        for cancellation in (False, True):
            process = FakeLoginProcess(delay=10)
            async def run():
                spec = {"action": "login", "timeout": 10 if cancellation else 0.02}
                task = asyncio.create_task(self.bridge.run_operation(spec, self.directory))
                if cancellation:
                    await asyncio.sleep(0.01)
                    task.cancel()
                with self.assertRaises(asyncio.CancelledError if cancellation
                                       else self.bridge.BackendError):
                    await task
            with mock.patch.object(self.bridge, "resolve_cli", return_value="native-copilot"), \
                    mock.patch.object(self.bridge.asyncio, "create_subprocess_exec",
                                      mock.AsyncMock(return_value=process)):
                asyncio.run(run())
            self.assertTrue(process.terminated)

    def test_failed_browser_login_has_static_actionable_error(self):
        with mock.patch.object(self.bridge, "resolve_cli", return_value="native-copilot"), \
                mock.patch.object(self.bridge.asyncio, "create_subprocess_exec",
                                  mock.AsyncMock(return_value=FakeLoginProcess(code=1))):
            with self.assertRaises(self.bridge.BackendError) as caught:
                self.operation(None, "login")
        self.assertEqual(caught.exception.kind, "auth")
        self.assertIn("copilot login", caught.exception.detail)

    def test_text_only_session_isolated_from_tools_and_repository(self):
        client = FakeClient()
        result = self.operation(client)
        self.assertEqual(result["provider"], "copilot")
        self.assertEqual(result["model"], "test-model")
        self.assertEqual(result["text"], "proposal only")
        self.assertIsNone(result["usage"])
        self.assertEqual(client.options["model"], "test-model")
        self.assertEqual(client.options["available_tools"], [])
        self.assertEqual(client.options["tools"], [])
        self.assertEqual(client.options["mcp_servers"], {})
        self.assertEqual(client.options["custom_agents"], [])
        self.assertEqual(client.options["skill_directories"], [])
        for flag in ("enable_config_discovery", "enable_file_hooks", "enable_skills",
                     "enable_host_git_operations", "enable_session_store",
                     "enable_on_demand_instruction_discovery"):
            self.assertFalse(client.options[flag], flag)
        self.assertTrue(client.options["skip_custom_instructions"])
        self.assertEqual(client.options["memory"], {"enabled": False})
        self.assertEqual(client.options["system_message"],
                         {"mode": "replace", "content": "Approved system only"})
        self.assertEqual(Path(client.options["working_directory"]), self.directory / "workspace")
        self.assertEqual(client.prompts, [
            '[{"role":"user","content":"Approved context"},'
            '{"role":"assistant","content":"Earlier answer"}]'])
        self.assertTrue(client.stopped)
        self.assertTrue(client.disconnected)
        reject = types.SimpleNamespace(PermissionDecisionReject=lambda: types.SimpleNamespace(kind="reject"))
        with mock.patch.dict("sys.modules", {"copilot.generated.rpc": reject}):
            self.assertEqual(self.bridge.deny_permission(None, None).kind, "reject")

    def test_unknown_disabled_and_auto_models_never_generate(self):
        for model in ("missing", "blocked-model", "auto"):
            client = FakeClient()
            with self.assertRaises(self.bridge.BackendError) as caught:
                self.operation(client, model=model)
            self.assertEqual(caught.exception.kind, "unavailableModel")
            self.assertEqual(client.prompts, [])

    def test_model_fallback_is_rejected_before_generation(self):
        client = FakeClient(current_model="different-model")
        with self.assertRaises(self.bridge.BackendError) as caught:
            self.operation(client)
        self.assertEqual(caught.exception.kind, "unavailableModel")
        self.assertEqual(client.prompts, [])
        self.assertTrue(client.stopped)

    def test_runtime_that_ignores_tool_disabling_is_rejected_before_generation(self):
        client = FakeClient(tools=["shell"])
        with self.assertRaises(self.bridge.BackendError) as caught:
            self.operation(client)
        self.assertEqual(caught.exception.kind, "config")
        self.assertEqual(client.prompts, [])
        self.assertTrue(client.stopped)

    def test_missing_auth_does_not_create_session(self):
        client = FakeClient(authenticated=False)
        with self.assertRaises(self.bridge.BackendError) as caught:
            self.operation(client)
        self.assertEqual(caught.exception.kind, "auth")
        self.assertIsNone(client.options)
        self.assertTrue(client.stopped)

    def test_timeout_aborts_generation_and_stops_runtime(self):
        client = FakeClient(delay=1)
        with self.assertRaises(self.bridge.BackendError) as caught:
            self.operation(client, timeout=0.05)
        self.assertEqual(caught.exception.kind, "network")
        self.assertTrue(client.aborted)
        self.assertTrue(client.stopped)

    def test_cancellation_aborts_and_releases_sdk_child(self):
        client = FakeClient(delay=10)
        async def cancel():
            spec = {"action": "complete", "timeout": 20, "request": {
                "model": "test-model", "messages": [{"role": "user", "content": "approved"}]}}
            task = asyncio.create_task(self.bridge.run_operation(
                spec, self.directory, lambda: client))
            await asyncio.sleep(0.01)
            task.cancel()
            with self.assertRaises(asyncio.CancelledError):
                await task
        asyncio.run(cancel())
        self.assertTrue(client.aborted)
        self.assertTrue(client.stopped)

    def test_runtime_errors_never_expose_exception_text_or_tokens(self):
        key = "ghu_private_fake_token"
        client = FakeClient(error="HTTP 401 Authorization: Bearer " + key)
        with self.assertRaises(self.bridge.BackendError) as caught:
            self.operation(client)
        self.assertEqual(caught.exception.kind, "auth")
        self.assertNotIn(key, str(caught.exception))
        self.assertTrue(client.stopped)


class CopilotProviderTests(unittest.TestCase):
    def test_default_provider_uses_saved_copilot_runtime_paths(self):
        python_path = str(BUILD_DIR / "copilot-runtime" / "bin" / "python")
        cli_path = str(BUILD_DIR / "native-copilot")
        body = r"""
		var provider;
		MBProviderPaths.writeJSON(MBProviderPaths.settingsDir +/+ "copilot-runtime.json",
			(pythonPath: %PYTHON%, cliPath: %CLI%));
		provider = MBCopilotProvider.new;
		~emit.(\paths, [provider.pythonPath, provider.cliPath]);
		""".replace("%PYTHON%", sc_string(python_path)).replace(
            "%CLI%", sc_string(cli_path))
        run = run_sclang("copilot_runtime_paths", body)
        self.assertEqual(run.get("paths"), [python_path, cli_path])

    def test_provider_picks_up_runtime_setup_without_restarting_scide(self):
        python_path = str(Path(sys.executable))
        cli_path = str(BUILD_DIR / "native-copilot")
        helper = ROOT / "tests" / "mb_providers" / "fake_copilot_bridge.py"
        body = r"""
		var provider;
		provider = MBCopilotProvider.new(nil, nil, 10, %HELPER%);
		MBProviderPaths.writeJSON(MBProviderPaths.settingsDir +/+ "copilot-runtime.json",
			(pythonPath: %PYTHON%, cliPath: %CLI%));
		~emit.(\auth, ~await.({ |done| provider.authStatus(done, done) }));
		~emit.(\paths, [provider.pythonPath, provider.cliPath]);
		""".replace("%HELPER%", sc_string(str(helper))).replace(
            "%PYTHON%", sc_string(python_path)).replace("%CLI%", sc_string(cli_path))
        run = run_sclang("copilot_runtime_refresh", body)
        self.assertEqual(run.get("auth"), [{"authenticated": True}])
        self.assertEqual(run.get("paths"), [python_path, cli_path])

    def test_missing_optional_runtime_is_an_actionable_error_without_generation(self):
        body = r"""
		var provider = MBCopilotProvider.new(%PYTHON%, %MISSING%, 5);
		~emit.(\error, ~await.({ |done| provider.authStatus(
			{ done.(\unexpectedSuccess) }, { |e| done.(~errInfo.(e)) }) }));
		~emit.(\loginError, ~await.({ |done| provider.login(
			{ done.(\unexpectedSuccess) }, { |e| done.(~errInfo.(e)) }) }));
		""".replace("%PYTHON%", sc_string(sys.executable)).replace(
            "%MISSING%", sc_string(str(BUILD_DIR / "nonexistent-copilot-executable")))
        run = run_sclang("copilot_unavailable", body)
        error = run.get("error")[0]
        self.assertEqual(error["kind"], "config")
        self.assertTrue(any(word in error["detail"].lower()
                            for word in ("python", "dependencies", "install")))
        helper = {
            "darwin": "setup-copilot.command",
            "linux": "setup-copilot.sh",
            "win32": "Setup-Copilot.cmd",
        }.get(sys.platform)
        if helper:
            self.assertIn(helper.lower(), error["detail"].lower())
        self.assertEqual(run.get("loginError")[0]["kind"], "config")
        self.assertIn("GitHub Copilot CLI", run.get("loginError")[0]["detail"])

    def test_provider_contract_model_selection_unknown_pricing_and_cancel(self):
        helper = ROOT / "tests" / "mb_providers" / "fake_copilot_bridge.py"
        body = r"""
		var provider, request, result, h, calls = 0;
		provider = MBCopilotProvider.new(%PYTHON%, nil, 10, %HELPER%);
		request = (model: "test-model", system: "approved",
			messages: [(role: \user, content: "approved context")],
			maxOutputTokens: 100);
		~emit.(\identity, [provider.id, provider.requiresApiKey]);
		~emit.(\login, ~await.({ |done| provider.login(done, done) }));
		~emit.(\auth, ~await.({ |done| provider.authStatus(done, done) }));
		~emit.(\models, ~await.({ |done| provider.listModels(done, done) }));
		result = ~await.({ |done| provider.complete(request, done, done) })[0];
		~emit.(\result, result);
		~emit.(\cost, MBUsageMeter.new.record(result));
		~emit.(\missing, ~await.({ |done| provider.complete(request.copy.put(\model, "missing"),
			done, { |e| done.(~errInfo.(e)) }) }));
		~emit.(\cancel, ~await.({ |done|
			h = provider.complete(request.copy.put(\model, "slow"),
				{ calls = calls + 1; done.(\ok) },
				{ |e| calls = calls + 1; done.(~errInfo.(e)) });
			AppClock.sched(0.2, { h.cancel; nil });
		}));
		0.5.wait;
		~emit.(\calls, calls);
		""".replace("%PYTHON%", sc_string(sys.executable)).replace(
            "%HELPER%", sc_string(str(helper)))
        run = run_sclang("copilot_provider", body)
        self.assertEqual(run.get("identity"), ["copilot", False])
        self.assertEqual(run.get("login"), [{"authenticated": True}])
        self.assertEqual(run.get("auth"), [{"authenticated": True}])
        self.assertEqual(run.get("models")[0][0]["id"], "test-model")
        self.assertEqual(run.get("models")[0][0]["displayName"], "Fake Copilot")
        self.assertEqual(run.get("result")["provider"], "copilot")
        self.assertEqual(run.get("result")["model"], "test-model")
        self.assertEqual(run.get("result")["text"], "proposal only")
        self.assertEqual(run.get("cost")["rateStatus"], "missing")
        self.assertIsNone(run.get("cost").get("usd"))
        self.assertEqual(run.get("missing")[0]["kind"], "unavailableModel")
        self.assertEqual(run.get("cancel")[0]["kind"], "cancelled")
        self.assertEqual(run.get("calls"), 1)
