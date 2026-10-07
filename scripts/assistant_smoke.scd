// MaxxedBeats assistant smoke test against an INSTALLED copy (run by
// scripts/ci_assistant_smoke.py). sclang runs without --include-path, so the
// MaxxedBeats Quark and ChaosOsc must compile from the Extensions folder
// SuperCollider scans by itself. Offline: the mock DJ proposes a ChaosOsc
// composition, it is applied (confirmed), then rendered (approved) with the
// renderer's default tools and plugin paths, i.e. the installed ChaosOsc.
// argv: workDir expectedExtensionsDir("" to skip) platformStore("1" to query the OS store)
(
var args = thisProcess.argv, work = args[0], expected = args[1] ? "", queryStore = args[2] == "1";
var failures = 0, check, await, inside;
check = { |name, condition, detail = ""|
	if(condition == true) { ("MBSMOKE PASS " ++ name).postln } {
		failures = failures + 1;
		("MBSMOKE FAIL " ++ name ++ " :: " ++ detail.asString.replace("\n", " ").keep(1500)).postln;
	};
	condition == true
};
await = { |fn, timeout = 60|
	var condition = Condition(false), outcome;
	AppClock.sched(timeout, { if(outcome.isNil) { outcome = [\timeout]; condition.test = true; condition.signal }; nil });
	fn.value(
		{ |value| if(outcome.isNil) { outcome = [\ok, value]; condition.test = true; condition.signal } },
		{ |error| if(outcome.isNil) { outcome = [\fail, error]; condition.test = true; condition.signal } });
	condition.wait;
	outcome
};
inside = { |path, dir|
	MBProject.comparablePath(path).beginsWith(MBProject.comparablePath(dir.withoutTrailingSlash) ++ "/")
};
AppClock.sched(600, { "MBSMOKE FAIL watchdog :: timed out".postln; "MBSMOKE DONE failures=1".postln; 1.exit; nil });

Routine {
	var registry, mock, catalog, meter, project, agent, outcome, proposal, result, window, store, describe;
	describe = { |o| o.collect { |item| if(item.isKindOf(Error)) { item.errorString } { item.asString.keep(600) } } };
	try {
		check.("classes_installed",
			[\MaxxedBeats, \MBAgent, \MBRenderer, \MBWindowsCredentialStore, \ChaosOsc].every { |name| name.asClass.notNil });
		("MBSMOKE INFO userExtensionDir=" ++ Platform.userExtensionDir).postln;
		("MBSMOKE INFO MaxxedBeats=" ++ MaxxedBeats.filenameSymbol ++ " ChaosOsc=" ++ \ChaosOsc.asClass.filenameSymbol).postln;
		if(expected.size > 0) {
			check.("installed_copy_in_use",
				inside.(MaxxedBeats.filenameSymbol.asString, expected)
				and: { inside.(\ChaosOsc.asClass.filenameSymbol.asString, expected) },
				[MaxxedBeats.filenameSymbol, \ChaosOsc.asClass.filenameSymbol]);
			check.("agent_instructions_installed", inside.(MBAgent.findInstructionsDir, expected), MBAgent.findInstructionsDir);
			check.("renderer_uses_installed_chaososc",
				MBRenderer.chaosOscPluginDirs.size == 1
				and: { inside.(MBRenderer.chaosOscPluginDirs[0] +/+ "ChaosOsc.scx", expected) }
				and: { MBRenderer.uniqueDirs(MBRenderer.extensionPluginPaths).any { |dir|
					inside.(MBRenderer.chaosOscPluginDirs[0] +/+ "x", dir) } },
				[MBRenderer.chaosOscPluginDirs, MBRenderer.extensionPluginPaths]);
		};
		check.("agent_instructions_load", MBAgent.systemPrompt.contains("agent/SAFETY.md"));

		store = MBCredentialStore.default;
		check.("platform_credential_backend",
			store.class == switch(thisProcess.platform.name,
				\windows, { MBWindowsCredentialStore }, \osx, { MBKeychainCredentialStore }, { MBSecretServiceCredentialStore }),
			store);
		if(queryStore) {
			// Read-only query of the real store (Windows: PowerShell helper + Credential Manager).
			outcome = await.({ |ok| store.hasKey(\openai, ok) });
			check.("credential_store_query", outcome[0] == \ok and: { outcome[1].isKindOf(Boolean) }, describe.(outcome));
		};

		registry = MBProviderRegistry.new(MBCredentialStore.fake);
		mock = registry.at(\mock);
		catalog = MBModelCatalog.new(registry, work +/+ "settings");
		meter = MBUsageMeter.new(historyPath: work +/+ "settings" +/+ "usage-history.json");
		outcome = await.({ |ok, fail| catalog.refresh(\mock, ok, fail) });
		check.("mock_models", outcome[0] == \ok, describe.(outcome));
		check.("select_model", catalog.selectModel(\mock, "mock-composer-1").isNil);

		File.mkdir(work +/+ "project");
		project = MBProject.open(work +/+ "project");
		agent = MBAgent(project, mock, catalog, meter);
		outcome = await.({ |ok, fail| agent.propose("Make a short ChaosOsc groove", (), ok, fail) });
		check.("propose", outcome[0] == \ok and: { outcome[1][\edits].notEmpty }, describe.(outcome));
		proposal = outcome[1];
		if(outcome[0] == \ok) {
			outcome = await.({ |ok, fail| project.apply(proposal, true, ok, fail) });
			check.("apply_confirmed", outcome[0] == \ok, describe.(outcome));
			outcome = await.({ |ok, fail|
				MBRenderer.render(project, proposal[\entry] ? project.files.detect { |f| f.endsWith(".scd") },
					(duration: 2.0, seed: proposal[\seed] ? 0.5, timeout: 240), true, nil, ok, fail)
			}, 480);
			check.("render_with_installed_chaososc", outcome[0] == \ok, describe.(outcome));
			if(outcome[0] == \ok) {
				result = outcome[1];
				("MBSMOKE INFO wav=" ++ result[\path]).postln;
				check.("render_checks", File.exists(result[\path]) and: { result[\checks][\finite] }
					and: { result[\checks][\silent].not } and: { result[\checks][\durationOk] }
					and: { File.exists(result[\metadataPath]) }, result[\checks]);
			};
		};

		window = MaxxedBeats.gui(MaxxedBeats.services(nil, (store: MBCredentialStore.fake, registry: registry)));
		0.5.wait;
		check.("gui_opens", window.window.isClosed.not and: { window.views[\djLabel].string == "Choose your DJ" });
		window.close;
		0.2.wait;
	} { |error|
		check.("uncaught_error", false, error.errorString);
	};
	("MBSMOKE DONE failures=" ++ failures).postln;
	AppClock.sched(0.2, { if(failures == 0) { 0.exit } { 1.exit }; nil });
}.play(AppClock);
)
