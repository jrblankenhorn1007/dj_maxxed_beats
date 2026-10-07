// Optional official Copilot SDK/runtime backend, using the CLI's own login.
// The helper runs in an empty directory with tools and discovery disabled.
MBCopilotProvider : MBProvider {
	var <pythonPath, <cliPath, <bridgePath, pythonOverride, cliOverride;

	*new { |pythonPath, cliPath, timeout = 120, bridgePath|
		^super.new.prInitCopilot(pythonPath, cliPath, timeout, bridgePath)
	}

	prInitCopilot { |argPython, argCli, argTimeout, argBridge|
		id = \copilot;
		displayName = "GitHub Copilot";
		timeout = argTimeout;
		pythonOverride = argPython;
		cliOverride = argCli;
		bridgePath = argBridge ? (MBProviderPaths.dataDir +/+ "copilot" +/+ "bridge.py");
		this.prLoadRuntime;
	}

	prLoadRuntime {
		var runtime = MBProviderPaths.readJSON(MBProviderPaths.copilotRuntimePath),
			configuredPython, configuredCli;
		configuredPython = if(runtime.isKindOf(Dictionary)) { runtime["pythonPath"] };
		configuredCli = if(runtime.isKindOf(Dictionary)) { runtime["cliPath"] };
		pythonPath = pythonOverride ? configuredPython
			? if(MBProviderPaths.isWindows) { "python" } { "python3" };
		cliPath = cliOverride ? configuredCli;
	}

	requiresApiKey { ^false }

	// Only call from an explicit user action: the official CLI opens a browser
	// and owns the OAuth exchange and credential storage.
	login { |onSuccess, onFailure|
		^this.prRunCopilot("login", nil, onSuccess, onFailure)
	}

	authStatus { |onSuccess, onFailure|
		^this.prRunCopilot("auth", nil, onSuccess, onFailure)
	}

	listModels { |onSuccess, onFailure|
		^this.prRunCopilot("models", nil, onSuccess, onFailure)
	}

	complete { |request, onSuccess, onFailure|
		var error = this.class.checkRequest(request), handle;
		if(error.notNil) {
			handle = this.prNewHandle(onFailure);
			^this.prFailLater(handle, error, onFailure)
		};
		^this.prRunCopilot("complete", request, onSuccess, onFailure)
	}

	prRunCopilot { |action, request, onSuccess, onFailure|
		var dir = MBProviderPaths.newRunDir, handle = this.prNewHandle(onFailure),
			error, argv, script;
		this.prLoadRuntime;
		error = MBProviderPaths.writeJSON(dir +/+ "copilot-request.json",
			(action: action, request: request, timeout: timeout, cli: cliPath));
		if(error.notNil) {
			MBProviderPaths.removeDir(dir);
			^this.prFailLater(handle, error, onFailure)
		};
		argv = [pythonPath, bridgePath, "--run-dir", dir];
		script = if(MBProviderPaths.isWindows) { argv } {
			"umask 077\n" ++ argv.collect(_.shellQuote).join(" ")
		};
		handle.inner = MBProcess.run(script, dir, nil, timeout + 5, { |code, why|
			var envelope = MBProviderPaths.readJSON(dir +/+ "copilot-response.json"), result, failure;
			failure = case
			{ why == \timeout } { MBError(\network, "Copilot request timed out") }
			{ why == \cancelled } { MBError(\cancelled, "Request cancelled") }
			{ code != 0 or: { envelope.isKindOf(Dictionary).not } } {
				MBError(\config, "GitHub Copilot is not set up yet. Run the included "
					++ "Copilot setup helper, then try again.")
			}
			{ envelope["error"].notNil } {
				MBError(envelope["error"]["kind"].asSymbol,
					MBRedact.string(envelope["error"]["detail"]))
			}
			{ nil };
			if(failure.isNil) { result = this.prSymbolize(envelope["result"]) };
			MBProviderPaths.removeDir(dir);
			if(handle.finish) {
				if(failure.notNil) { onFailure.value(failure) } { onSuccess.value(result) }
			};
		});
		^handle
	}

	prSymbolize { |value|
		var result;
		if(value.isKindOf(Dictionary)) {
			result = Event.new;
			value.keysValuesDo { |key, item| result[key.asSymbol] = this.prSymbolize(item) };
			if(result[\provider].notNil) { result[\provider] = result[\provider].asSymbol };
			^result
		};
		if(value.isArray) { ^value.collect { |item| this.prSymbolize(item) } };
		^value
	}
}
