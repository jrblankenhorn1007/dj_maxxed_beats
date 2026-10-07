// Entry point, service factory, audition, and help tests (run by
// tests/test_mb_gui.py with --include-path tests/mb_gui/stubs).
(
var here = thisProcess.nowExecutingPath.dirname;
var repo = here.dirname.dirname;
var makeFakes = (here +/+ "fake_services.scd").load;
var passes = 0, failures = 0;
var check = { |label, condition, detail|
	if(condition == true) {
		passes = passes + 1;
		("MBTEST PASS " ++ label).postln;
	} {
		failures = failures + 1;
		("MBTEST FAIL " ++ label ++ " :: " ++ (detail ? "")).postln;
	};
};
var stubLookup = { |name| ("MBTestStub" ++ name.asString.drop(2)).asSymbol.asClass };
var results = IdentityDictionary.new;
var record = { |key| { |...args| results[key] = args } };
var s, error, f, w, w2, c, tmpWav, helpFiles;

try {
	// Missing worker classes are a clear configuration error, never a crash.
	error = nil;
	try { MaxxedBeats.services({ |name| nil }) } { |e| error = e };
	check.("factory/missingClassesIsConfigError", error.isKindOf(MBError) and: { error.kind == \config }, error.cs);
	check.("factory/missingClassesNamed", error.notNil and: { error.detail.contains("MBProviderRegistry") }, error.cs);

	s = MaxxedBeats.services(stubLookup);
	MBTestStubLog.reset;
	check.("factory/providers", s[\providers].value.collect { |p| p[\id] } == [\openai, \anthropic, \mock]);
	check.("factory/mockNeedsNoKey", s[\providers].value.detect { |p| p[\id] == \mock }[\requiresKey] == false);
	check.("factory/displayName", s[\providers].value[0][\displayName] == "OpenAI");
	s[\hasKey].value(\openai, record.(\hasKey));
	check.("factory/hasKey", results[\hasKey] == [true]);
	s[\storeKey].value(\openai, "sk-stub-0000000000", record.(\stored), record.(\storeFailed));
	check.("factory/storeKey", results[\stored].notNil and: { MBTestStubLog.of(\storeKey)[0] == [\storeKey, \openai, 18] });
	s[\validateKey].value(\openai, record.(\valid), record.(\invalid));
	check.("factory/validateKeyFailure", results[\invalid][0].kind == \auth);
	s[\removeKey].value(\openai, record.(\removed), nil);
	check.("factory/removeKey", results[\removed].notNil);
	s[\refreshModels].value(\openai, record.(\refreshed), nil);
	check.("factory/refresh", MBTestStubLog.of(\refresh).size == 1 and: { results[\refreshed].notNil });
	check.("factory/models", s[\models].value(\openai)[0][\id] == "stub-model");
	check.("factory/catalogState", s[\lastRefreshed].value(\openai) == "2026-10-06" and: { s[\isStale].value(\openai) == false });
	s[\selectModel].value(\openai, "stub-model");
	check.("factory/selectModel", s[\selectedModel].value(\openai) == "stub-model");
	check.("factory/usage", s[\sessionTotals].value[\requests] == 0 and: { s[\history].value == [] });
	s[\openProject].value("/missing", record.(\opened), record.(\openFailed));
	check.("factory/openFailure", results[\openFailed][0].kind == \io);
	s[\openProject].value("/stub/project", record.(\opened), record.(\openFailed));
	check.("factory/open", results[\opened][0][\root] == "/stub/project"
		and: { results[\opened][0][\files] == ["main.scd", "notes.txt"] });

	s[\propose].value(results[\opened][0][\project], \openai, "other-model", "hi", (files: []), record.(\proposed), record.(\proposeFailed));
	check.("factory/proposeRefusesUnselectedModel", results[\proposeFailed].notNil
		and: { results[\proposeFailed][0].kind == \unavailableModel } and: { MBTestStubLog.of(\agentNew).isEmpty });
	results[\proposed] = nil;
	s[\propose].value(results[\opened][0][\project], \openai, "stub-model", "hi", (files: ["main.scd"]), record.(\proposed), record.(\proposeFailed));
	check.("factory/propose", results[\proposed].notNil and: { MBTestStubLog.of(\agentNew)[0][1] == \openai }
		and: { MBTestStubLog.of(\agentNew)[0][2] == \MBTestStubUsageMeter });
	s[\apply].value(results[\opened][0][\project], results[\proposed][0], true, record.(\applied), nil);
	check.("factory/apply", MBTestStubLog.of(\apply)[0] == [\apply, true]);
	s[\undo].value(results[\opened][0][\project], record.(\undone), nil);
	check.("factory/undo", results[\undone].notNil);
	results[\handle] = s[\render].value(results[\opened][0][\project], "main.scd", (duration: 3, sampleRate: 48000, numChannels: 2), true, record.(\progress), record.(\rendered), nil);
	check.("factory/render", MBTestStubLog.of(\render)[0] == [\render, "main.scd", true, 3] and: { results[\progress] == [0.5] });
	s[\cancel].value(results[\handle]);
	check.("factory/cancel", MBTestStubLog.of(\cancel)[0] == [\cancel, \render]);
	results[\session] = s[\startVariations].value(results[\opened][0][\project], \openai, "stub-model", "vary", 3, record.(\candidate), record.(\done), nil);
	check.("factory/variationsStart", MBTestStubLog.of(\sessionNew)[0] == [\sessionNew, 3] and: { results[\candidate].notNil });
	s[\stopVariations].value(results[\session]);
	s[\applyVariation].value(results[\session], 0, true, record.(\varApplied), nil);
	check.("factory/variationsStopApply", MBTestStubLog.of(\sessionStop).size == 1 and: { MBTestStubLog.of(\sessionApply)[0] == [\sessionApply, 0, true] });
	s[\clearHistory].value;
	check.("factory/clearHistory", MBTestStubLog.of(\clearHistory).size == 1);

	// Real playback never boots a server or plays a missing file.
	s[\play].value("/definitely/missing.wav", record.(\playStarted), nil, record.(\playFailed));
	check.("audition/missingFile", results[\playFailed][0].kind == \io and: { results[\playStarted].isNil });
	tmpWav = Platform.defaultTempDir +/+ "mb-entry-test.wav";
	File.use(tmpWav, "w", { |file| file.write("RIFF") });
	s[\play].value(tmpWav, record.(\playStarted), nil, record.(\playFailed2));
	check.("audition/serverNotRunning", results[\playFailed2][0].kind == \config
		and: { results[\playFailed2][0].detail.contains("s.boot") } and: { Server.default.serverRunning.not });
	File.delete(tmpWav);

	// The SCIDE entry point opens one window and fronts it on repeat calls.
	f = makeFakes.value;
	w = MaxxedBeats.gui(f[\services]);
	check.("entry/opens", w.isKindOf(MBGuiWindow) and: { w.window.isClosed.not });
	check.("entry/current", MaxxedBeats.current === w);
	w2 = MaxxedBeats.gui;
	check.("entry/reuses", w2 === w);
	w.close;
	check.("entry/closedCleared", MaxxedBeats.current.isNil);

	// Missing classes open the window with a visible configuration error.
	w = MaxxedBeats.gui(MaxxedBeats.unavailableServices(MBError(\config, "classes missing")));
	check.("entry/unavailableShowsError", w.controller.error.notNil
		and: { w.controller.error.kind == \config } and: { w.isShown(\errorRow) });
	w.views[\projectPath].string = "/x";
	w.views[\openProject].doAction;
	check.("entry/unavailableActionsFail", w.controller.project.isNil and: { w.controller.error.kind == \config });
	w.close;

	// The factory wired into the real window works end to end with stubs.
	w = MaxxedBeats.gui(MaxxedBeats.services(stubLookup));
	c = w.controller;
	w.views[\projectPath].string = "/stub/project";
	w.views[\openProject].doAction;
	w.views[\provider].valueAction = w.views[\provider].items.detectIndex { |i| i.contains("(mock)") };
	w.views[\prompt].string = "stub prompt";
	w.views[\send].doAction;
	check.("wired/proposal", c.proposal.notNil and: { c.proposalState == \noEdits }, c.proposalState.cs);
	check.("wired/ids", w.views[\djIds].string.contains("stub-model"));
	w.close;

	// Help files parse with SCDoc.
	helpFiles = PathName(repo +/+ "extension/HelpSource").deepFiles.select { |p| p.extension == "schelp" };
	check.("help/present", helpFiles.size >= 2, helpFiles.size.asString);
	helpFiles.do { |p|
		check.("help/parses/" ++ p.fileName, SCDoc.parseFileFull(p.fullPath).notNil);
	};
} { |e|
	check.("exception", false, e.errorString);
};
("MBTEST DONE passes=" ++ passes ++ " failures=" ++ failures).postln;
0.exit;
)
