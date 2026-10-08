"""Optional official Copilot SDK bridge. No tokens, CLI prompts, or shell tools.

Requires Python >=3.11 and requirements.txt. The SDK uses its pinned stdio
runtime; the official CLI owns browser sign-in. This is not GitHub Models.
"""
import argparse
import asyncio
import json
import logging
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys


class BackendError(Exception):
    def __init__(self, kind, detail):
        super().__init__(detail)
        self.kind = kind
        self.detail = detail


def deny_permission(request, context):
    from copilot.generated.rpc import PermissionDecisionReject
    return PermissionDecisionReject()


def runtime_error(error):
    # Runtime exceptions may contain authentication headers or prompt content.
    # Classify them, but never copy their text to output, files, or logs.
    text = str(error).lower()
    if any(term in text for term in ("401", "403", "auth", "login", "token")):
        return BackendError("auth", "Copilot authentication failed; run copilot login.")
    if any(term in text for term in ("429", "quota", "rate limit", "credits")):
        return BackendError("rateLimit", "Copilot quota or subscription limit reached.")
    if "model" in text and any(term in text for term in ("not found", "unsupported", "unavailable")):
        return BackendError("unavailableModel", "The selected Copilot model is unavailable.")
    return BackendError("network", "Copilot runtime failed; check the CLI installation and connection.")


def native_cli_candidates():
    platform_name = {"darwin": "darwin", "win32": "win32", "linux": "linux"}.get(sys.platform)
    if platform_name is None:
        return
    home = Path.home()
    executable = "copilot.exe" if sys.platform == "win32" else "copilot"
    package_roots = [
        home / ".local" / "copilot-cli" / "lib" / "node_modules" / "@github" /
        "copilot" / "node_modules" / "@github",
        home / ".local" / "lib" / "node_modules" / "@github" /
        "copilot" / "node_modules" / "@github",
        home / ".npm-global" / "lib" / "node_modules" / "@github" /
        "copilot" / "node_modules" / "@github",
    ]
    if sys.platform == "win32":
        appdata = Path(os.environ.get("APPDATA", home / "AppData" / "Roaming"))
        package_roots.insert(
            0, appdata / "npm" / "node_modules" / "@github" /
            "copilot" / "node_modules" / "@github")
        local_appdata = Path(os.environ.get("LOCALAPPDATA", home / "AppData" / "Local"))
        package_roots.append(
            local_appdata / "npm" / "node_modules" / "@github" /
            "copilot" / "node_modules" / "@github")
        yield local_appdata / "Programs" / "GitHub Copilot" / executable
        program_files = Path(os.environ.get("ProgramFiles", "C:/Program Files"))
        yield program_files / "GitHub Copilot" / executable
    for root in package_roots:
        if root.is_dir():
            yield from root.glob("copilot-{}-*/{}".format(platform_name, executable))


def setup_helper_instruction():
    if sys.platform == "darwin":
        return ("Double-click setup-copilot.command in the installed "
                "MaxxedBeats/Data/copilot folder.")
    if sys.platform.startswith("linux"):
        return ("In the installed MaxxedBeats/Data/copilot folder, right-click "
                "setup-copilot.sh and choose Run in Terminal.")
    if sys.platform == "win32":
        return "Double-click Setup-Copilot.cmd in the extracted MaxxedBeats folder."
    return "Run the included Copilot setup helper."


def resolve_cli(spec):
    configured = spec.get("cli")
    if configured:
        cli = Path(configured).expanduser()
        if cli.is_file():
            return str(cli.resolve())
        raise BackendError(
            "config", "The saved GitHub Copilot CLI location no longer exists. "
            + setup_helper_instruction())
    environment_cli = os.environ.get("MBCOPILOT_CLI_PATH")
    if environment_cli:
        cli = Path(environment_cli).expanduser()
        if cli.is_file():
            return str(cli.resolve())
        raise BackendError(
            "config", "MBCOPILOT_CLI_PATH does not point to a file. "
            + setup_helper_instruction())
    for candidate in native_cli_candidates():
        if candidate.is_file():
            return str(candidate.resolve())
    cli = shutil.which("copilot")
    if cli and Path(cli).is_file():
        return str(Path(cli).resolve())
    raise BackendError(
        "config", "The official GitHub Copilot CLI was not found. "
        + setup_helper_instruction() + " Then try again.")


def runtime_environment():
    blocked_keys = {"GH_TOKEN", "GITHUB_TOKEN", "OPENAI_API_KEY", "ANTHROPIC_API_KEY"}
    return {
        key: value for key, value in os.environ.items()
        if not key.upper().startswith(("COPILOT_", "OTEL_"))
        and key.upper() not in blocked_keys
    }


async def run_login(spec, directory):
    cli = resolve_cli(spec)
    process = None
    try:
        options = {"cwd": str(directory / "workspace"), "env": runtime_environment(),
                   "stdin": subprocess.DEVNULL, "stdout": subprocess.DEVNULL,
                   "stderr": subprocess.DEVNULL}
        if os.name == "nt":
            options["creationflags"] = subprocess.CREATE_NO_WINDOW
        process = await asyncio.create_subprocess_exec(cli, "login", "--web-flow", **options)
        code = await asyncio.wait_for(process.wait(), timeout=float(spec.get("timeout", 120)))
        if code != 0:
            raise BackendError("auth", "Copilot browser sign-in did not complete. Retry, or run "
                               "copilot login in a terminal for the browser/device flow.")
        return {"authenticated": True}
    except asyncio.TimeoutError:
        raise BackendError("network", "Copilot browser sign-in timed out; retry sign-in.") from None
    except OSError:
        raise BackendError(
            "config", "Could not start the GitHub Copilot CLI. "
            + setup_helper_instruction()) from None
    finally:
        if process is not None and process.returncode is None:
            try:
                process.terminate()
            except ProcessLookupError:
                pass
            try:
                await asyncio.wait_for(process.wait(), timeout=1)
            except asyncio.TimeoutError:
                try:
                    process.kill()
                except ProcessLookupError:
                    pass
                await process.wait()


def sdk_client(directory):
    if sys.version_info < (3, 11):
        raise BackendError(
            "config", "Copilot requires Python 3.11+ and github-copilot-sdk==1.0.16. "
            "Git authorization does not install this runtime; Copilot does not use an API key. "
            + setup_helper_instruction())
    try:
        from importlib.metadata import version
        from copilot import CopilotClient, StdioRuntimeConnection
        if version("github-copilot-sdk") != "1.0.16":
            raise ImportError()
    except Exception:
        raise BackendError(
            "config", "Copilot's required Python SDK 1.0.16 is missing or incompatible. "
            "Git authorization does not install this runtime. "
            + setup_helper_instruction()) from None
    # Keep the user's saved auth home and leave client OpenTelemetry unset; any
    # telemetry config enables instrumentation. Session telemetry is disabled
    # separately in session_options.
    return CopilotClient(
        connection=StdioRuntimeConnection(),
        working_directory=str(directory / "workspace"),
        env=runtime_environment(), use_logged_in_user=True, log_level="none",
        enable_remote_sessions=False)


def session_options(request, directory):
    return {
        "model": request["model"], "available_tools": [], "tools": [],
        "on_permission_request": deny_permission,
        "system_message": {"mode": "replace", "content": request.get("system") or ""},
        "working_directory": str(directory / "workspace"),
        "config_directory": str(directory / "config"),
        "enable_config_discovery": False, "skip_custom_instructions": True,
        "refresh_custom_instructions": False,
        "enable_on_demand_instruction_discovery": False,
        "enable_file_hooks": False, "enable_host_git_operations": False,
        "enable_session_store": False, "enable_session_telemetry": False,
        "enable_skills": False,
        "skip_embedding_retrieval": True, "enable_file_change_tracking": False,
        "skill_directories": [], "instruction_directories": [], "plugin_directories": [],
        "included_builtin_skills": [], "custom_agents": [], "custom_agents_local_only": True,
        "mcp_servers": {},
        "organization_custom_instructions": "", "additional_directories": [],
        "memory": {"enabled": False}, "infinite_sessions": {"enabled": False},
        "streaming": False,
    }


async def run_operation(spec, directory, client_factory=None):
    directory = Path(directory)
    for name in ("workspace", "config"):
        (directory / name).mkdir(exist_ok=True)
    client = session = None
    timeout = float(spec.get("timeout", 120))
    if timeout <= 0:
        raise BackendError("validation", "Copilot timeout must be positive.")
    if spec["action"] == "login":
        return await run_login(spec, directory)

    async def operation():
        nonlocal client, session
        client = client_factory() if client_factory else sdk_client(directory)
        await client.start()
        auth = await client.get_auth_status()
        if spec["action"] == "auth":
            return {"authenticated": bool(auth.isAuthenticated)}
        if not auth.isAuthenticated:
            raise BackendError("auth", "Copilot is not signed in; run copilot login.")
        models = [{
            "id": model.id, "displayName": model.name, "provider": "copilot",
            "usable": model.id != "auto" and (
                model.policy is None or model.policy.state == "enabled"),
            "note": "Copilot subscription; token cost unknown",
        } for model in await client.list_models()]
        if spec["action"] == "models":
            return models
        if spec["action"] != "complete":
            raise BackendError("validation", "Unknown Copilot operation.")
        request = spec["request"]
        selected = request["model"]
        if not any(model["id"] == selected and model["usable"] for model in models):
            raise BackendError("unavailableModel", "The selected Copilot model is unavailable; "
                               "refresh the model list. Automatic model selection is disabled.")
        session = await client.create_session(**session_options(request, directory))
        metadata = await session.rpc.tools.get_current_metadata()
        if metadata.tools:
            raise BackendError("config", "Copilot runtime did not disable every tool; "
                               "generation was refused. Update the official CLI.")
        current = await session.rpc.model.get_current()
        if current.model_id != selected:
            raise BackendError("unavailableModel", "Copilot did not select the requested model; "
                               "generation was refused.")
        # A JSON transcript preserves roles and order without inventing prior
        # runtime turns or letting earlier assistant text execute as instructions.
        prompt = json.dumps(request["messages"], ensure_ascii=False, separators=(",", ":"))
        answer = await session.send_and_wait(prompt, timeout=timeout)
        current = await session.rpc.model.get_current()
        if current.model_id != selected:
            raise BackendError("unavailableModel", "Copilot changed models; the response was refused.")
        if answer is None or not isinstance(answer.data.content, str):
            raise BackendError("parse", "Copilot returned no assistant text.")
        return {"provider": "copilot", "model": selected, "text": answer.data.content,
                "usage": None, "responseId": session.session_id, "stopReason": "completed"}

    try:
        return await asyncio.wait_for(operation(), timeout=timeout)
    except asyncio.TimeoutError:
        raise BackendError("network", "Copilot request timed out.") from None
    except asyncio.CancelledError:
        raise
    except BackendError:
        raise
    except Exception as error:
        raise runtime_error(error) from None
    finally:
        if session is not None:
            # Abort is safe even after idle; it bounds outstanding generations
            # on errors/timeouts, before releasing the isolated runtime.
            try:
                await asyncio.wait_for(session.abort(), timeout=1)
                await asyncio.wait_for(session.disconnect(), timeout=1)
            except Exception:
                pass
        if client is not None:
            try:
                await asyncio.wait_for(client.stop(), timeout=2)
            except Exception:
                pass


async def execute(spec, directory):
    task = asyncio.create_task(run_operation(spec, directory))
    loop = asyncio.get_running_loop()
    registered = False
    if os.name != "nt":
        # MBProcess sends SIGTERM on POSIX. Abort the native SDK child before
        # leaving, rather than orphaning an in-flight Copilot generation.
        loop.add_signal_handler(signal.SIGTERM, task.cancel)
        registered = True
    try:
        return await task
    except asyncio.CancelledError:
        raise BackendError("cancelled", "Copilot request cancelled.") from None
    finally:
        if registered:
            loop.remove_signal_handler(signal.SIGTERM)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", required=True)
    args = parser.parse_args()
    directory = Path(args.run_dir).resolve()
    logging.disable(logging.CRITICAL)
    try:
        spec = json.loads((directory / "copilot-request.json").read_text(encoding="utf-8"))
        envelope = {"result": asyncio.run(execute(spec, directory))}
    except BackendError as error:
        envelope = {"error": {"kind": error.kind, "detail": error.detail}}
    except Exception:
        envelope = {"error": {"kind": "config", "detail": "Could not start the Copilot bridge."}}
    partial = directory / "copilot-response.partial"
    partial.write_text(json.dumps(envelope, ensure_ascii=False), encoding="utf-8")
    partial.replace(directory / "copilot-response.json")
    partial = directory / "exit-code.partial"
    partial.write_text("0", encoding="ascii")
    partial.replace(directory / "exit-code.txt")


if __name__ == "__main__":
    main()
