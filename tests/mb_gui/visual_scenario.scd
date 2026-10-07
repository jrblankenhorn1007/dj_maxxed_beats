// Visual smoke scenario driver (opt-in; run by tests/mb_gui/capture_screenshots.py).
// Opens the real agent window through the SCIDE entry point
// (MaxxedBeats.gui) with deterministic offline fake services, drives the
// real widgets step by step, and before each screenshot prints
//   MB_CAPTURE_READY <name>
// then waits for <MB_VISUAL_OUT>/<name>.ack written by the capture script.
// No provider is contacted, no real key is used, nothing is rendered.
(
var here = thisProcess.nowExecutingPath.dirname;
var outDir = "MB_VISUAL_OUT".getenv ?? { Platform.defaultTempDir +/+ "mb-visual" };
var f = (here +/+ "fake_services.scd").load.value;
var w, v, c;
var press = { |key| v[key].doAction };
var choose = { |key, substring| v[key].valueAction = v[key].items.detectIndex { |i| i.contains(substring) } };
var capture = { |name|
	var ack = outDir +/+ name ++ ".ack", waited = 0;
	0.4.wait;
	("MB_CAPTURE_READY " ++ name).postln;
	while { File.exists(ack).not and: { waited < 60 } } { 0.1.wait; waited = waited + 0.1 };
	if(File.exists(ack).not) { ("MB_VISUAL_TIMEOUT " ++ name).postln };
};

f[\history].clear;
w = MaxxedBeats.gui(f[\services]);
v = w.views;
c = w.controller;
w.window.bounds = Rect(60, 60, 1180, 800);

fork({
	var step = { |name, function| function.value; capture.(name) };
	try {
		step.("01-opened", { choose.(\provider, "(mock)") });
		step.("02-request-in-flight", {
			v[\projectPath].string = "/Users/demo/MaxxedBeats Demo";
			press.(\openProject);
			v[\contextFiles].selection = [0];
			v[\prompt].string = "Make a warm 120 BPM techno groove with a ChaosOsc lead";
			press.(\send);
		});
		step.("03-proposal-diff", { f.succeedPropose });
		step.("04-confirm-apply", { press.(\approve) });
		step.("05-render-progress", {
			press.(\confirm);
			f.fire(\apply, 0, true);
			v[\duration].value = 4;
			press.(\render);
			press.(\confirm);
			f.fire(\render, 2, 0.45);
		});
		step.("06-render-result", { f.fire(\render, 0, f[\renderResult].value) });
		step.("07-usage", { press.(\tabUsage) });
		step.("08-error-state", {
			press.(\tabCompose);
			v[\prompt].string = "Add a breakdown";
			press.(\send);
			f.fire(\propose, 1, MBError(\network, "provider unreachable (fake): connection refused"));
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
			v[\varPrompt].string = "Darker bassline variations";
			v[\varMax].value = 4;
			press.(\varStart);
			2.do { |i| f.fire(\variations, 0, f[\candidate].value(i)) };
			press.(\varStop);
			v[\candidates].value = 0;
		});
	} { |error|
		("MB_VISUAL_ERROR " ++ error.errorString).postln;
	};
	"MB_VISUAL_DONE".postln;
	w.close;
	0.5.wait;
	0.exit;
}, AppClock);
)
