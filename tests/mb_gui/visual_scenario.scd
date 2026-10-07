// Visual smoke scenario driver (opt-in; run by tests/mb_gui/capture_screenshots.py,
// or evaluate in SCIDE for the visual sign-off).
// Opens the real agent window through MaxxedBeats.gui, wired by
// MaxxedBeats.services to the real classes with MBMockProvider (offline,
// deterministic) and an in-memory credential store, then drives the real
// widgets: propose, review, confirmed apply, approved real NRT render,
// usage, a provider error, masked key entry, and a rendered variation session.
// Before each screenshot it prints   MB_CAPTURE_READY <name>
// and waits for <MB_VISUAL_OUT>/<name>.ack. Without MB_VISUAL_OUT (SCIDE)
// each state is held for MB_VISUAL_STEP_SECONDS (default 5) and the window
// stays open; sclang exits only when MB_VISUAL_EXIT is "1".
// Optional: MB_VISUAL_PROJECT (default: a demo folder in the temp dir),
// MB_PLUGIN_DIR, MB_BUILTIN_PLUGIN_DIR, MB_SCLANG, MB_SCSYNTH (render tools;
// defaults: the installed ChaosOsc and this SuperCollider).
(
var outDir = "MB_VISUAL_OUT".getenv;
var stepSeconds = ("MB_VISUAL_STEP_SECONDS".getenv ? "5").asFloat;
var exitWhenDone = "MB_VISUAL_EXIT".getenv == "1";
var projectDir = "MB_VISUAL_PROJECT".getenv ?? { Platform.defaultTempDir +/+ "MaxxedBeats Visual Demo" };
var store = MBCredentialStore.fake;
var registry = MBProviderRegistry.new(store);
var mock = registry.at(\mock);
var w, v, c;
var press = { |key| v[key].doAction };
var choose = { |key, text| v[key].valueAction = v[key].items.detectIndex { |item| item.contains(text) } };
var waitFor = { |condition, timeout = 60|
	var waited = 0;
	while { condition.value.not and: { waited < timeout } } { 0.1.wait; waited = waited + 0.1 };
};
var capture = { |name|
	var ack, waited = 0;
	0.5.wait;
	("MB_CAPTURE_READY " ++ name).postln;
	if(outDir.isNil) { stepSeconds.wait } {
		ack = outDir +/+ name ++ ".ack";
		while { File.exists(ack).not and: { waited < 60 } } { 0.1.wait; waited = waited + 0.1 };
		if(File.exists(ack).not) { ("MB_VISUAL_TIMEOUT " ++ name).postln };
	};
};

"MB_PLUGIN_DIR".getenv !? { |dir| MBRenderer.defaultPluginPaths = [dir] };
"MB_BUILTIN_PLUGIN_DIR".getenv !? { |dir| MBRenderer.defaultBuiltinPluginPaths = [dir] };
"MB_SCLANG".getenv !? { |path| MBRenderer.defaultSclang = path };
"MB_SCSYNTH".getenv !? { |path| MBRenderer.defaultScsynth = path };
if(File.exists(projectDir +/+ "main.scd").not) {
	File.mkdir(projectDir);
	File.use(projectDir +/+ "main.scd", "w", { |f|
		f.write("// MaxxedBeats visual demo composition\n(\nvar def = SynthDef(\\mbDemoTone, { |out = 0|\n"
			++ "\tOut.ar(out, (SinOsc.ar(220) * 0.2) ! 2);\n});\nScore([\n\t[0.0, [\\d_recv, def.asBytes]],\n"
			++ "\t[0.0, [\\s_new, \\mbDemoTone, 1000, 0, 0]]\n])\n)\n")
	});
};

w = MaxxedBeats.gui(MaxxedBeats.services(nil, (store: store, registry: registry)));
v = w.views;
c = w.controller;
w.window.bounds = Rect(60, 60, 1180, 800);

fork({
	var step = { |name, function| function.value; capture.(name) };
	try {
		step.("01-opened", {
			choose.(\provider, "(mock)");
			press.(\refreshModels);
			waitFor.({ c.modelRefreshing.not and: { c.models.notEmpty } });
			choose.(\model, "mock-composer-1");
			v[\projectPath].string = projectDir;
			press.(\openProject);
			waitFor.({ c.project.notNil });
		});
		step.("02-request-in-flight", {
			mock.latency = 4;
			v[\contextFiles].selection = [c.projectFiles.indexOfEqual("main.scd") ? 0];
			v[\prompt].string = "Make a warm 120 BPM groove with a ChaosOsc lead";
			press.(\send);
		});
		step.("03-proposal-diff", { waitFor.({ c.busy.isNil }); mock.latency = 0 });
		step.("04-confirm-apply", { press.(\approve) });
		step.("05-render-progress", {
			press.(\confirm);
			waitFor.({ c.busy.isNil });
			v[\duration].value = 4;
			press.(\render);
			press.(\confirm);
			waitFor.({ c.busy.isNil or: { (c.progress ? 0) > 0.05 } });
		});
		step.("06-render-result", { waitFor.({ c.busy.isNil }, 180) });
		step.("07-usage", { press.(\tabUsage) });
		step.("08-error-state", {
			press.(\tabCompose);
			mock.enqueue(MBError(\network, "provider unreachable (mock): connection refused"));
			v[\prompt].string = "Add a breakdown";
			press.(\send);
			waitFor.({ c.busy.isNil });
		});
		step.("09-keys-masked", {
			press.(\dismissError);
			press.(\tabKeys);
			v[\keyField_openai].string = "sk-visual-FAKE-0000000000000000";
			w.masks[\openai].sync;
		});
		step.("10-variations", {
			w.masks[\openai].clear;
			press.(\tabVariations);
			v[\varPrompt].string = "Darker and sparser variations";
			v[\varMax].value = 2;
			v[\duration].value = 3;
			press.(\varStart);
			waitFor.({ c.variation[\running].not }, 300);
			c.variation[\candidates].do { |candidate, index|
				v[\candidates].value = index;
				press.(\renderCandidate);
				press.(\confirm);
				waitFor.({ c.busy.isNil }, 180);
			};
			v[\candidates].value = 0;
		});
	} { |error|
		("MB_VISUAL_ERROR " ++ error.errorString).postln;
	};
	if(c.error.notNil) { ("MB_VISUAL_NOTE last error: " ++ MBGuiFormat.errorText(c.error)).postln };
	"MB_VISUAL_DONE".postln;
	if(exitWhenDone) {
		w.close;
		0.5.wait;
		0.exit;
	};
}, AppClock);
)
