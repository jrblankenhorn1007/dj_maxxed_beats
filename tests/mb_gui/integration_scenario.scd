// End-to-end GUI integration scenario (run by tests/test_mb_integration.py).
// The real window (MaxxedBeats.gui) is wired by MaxxedBeats.services to the
// real provider/workflow classes with MBMockProvider (offline) and the
// in-memory fake credential store; renders are real separate-process NRT
// renders with ChaosOsc. Widgets are driven through their actions.
// argv: workDir repoRoot pluginDir builtinPluginDir sclang scsynth
(
var args = thisProcess.argv;
var here = thisProcess.nowExecutingPath.dirname;
(here.dirname +/+ "mb_workflow" +/+ "harness.scd").load;

~work = args[0];
~root = ~work +/+ "project";
MBRenderer.defaultPluginPaths = [args[2]];
MBRenderer.defaultBuiltinPluginPaths = [args[3]];
MBRenderer.defaultSclang = args[4];
MBRenderer.defaultScsynth = args[5];

AppClock.sched(900, { "MBTEST FAIL watchdog :: scenario timed out".postln; 1.exit; nil });

~read = { |path| var text; File.use(path, "r", { |f| text = f.readAllString }); text };
~snapshot = { (~root +/+ "*").pathMatch.select { |p| p.last.isPathSeparator.not }.collect { |p| [p.basename, ~read.(p)] } };
~waitFor = { |condition, timeout = 30|
	var waited = 0;
	while { condition.value.not and: { waited < timeout } } { 0.05.wait; waited = waited + 0.05 };
	condition.value
};
~press = { |key| ~v[key].doAction };
~choose = { |key, text| ~v[key].valueAction = ~v[key].items.detectIndex { |item| item.contains(text) } };
~allText = {
	~v.values.collect { |view|
		var text = "";
		if(view.respondsTo(\string)) { text = text ++ view.string.asString };
		if(view.respondsTo(\items)) { text = text ++ (view.items ? []).join("\n") };
		text
	}.join("\n")
};
~kind = { ~c.error !? { |e| e.kind } };
~idle = { ~c.busy.isNil };

~store = MBCredentialStore.fake;
~registry = MBProviderRegistry.new(~store);
~mockProvider = ~registry.at(\mock);
~services = MaxxedBeats.services(nil, (store: ~store, registry: ~registry));
~window = MaxxedBeats.gui(~services);
~v = ~window.views;
~c = ~window.controller;

Routine {
	var original, before, proposal, result, candidates, secret;
	try {
		~check.("window_open", ~window.window.isClosed.not and: { ~v[\djLabel].string == "Choose your DJ" });
		~check.("providers_listed", ~v[\provider].items.any { |i| i.contains("(mock)") }
			and: { ~v[\provider].items.any { |i| i.contains("(openai)") } }, ~v[\provider].items);

		// Choose your DJ: mock provider, refreshed list, explicit ids.
		~choose.(\provider, "(mock)");
		~press.(\refreshModels);
		~check.("models_refreshed", ~waitFor.({ ~c.modelRefreshing.not and: { ~c.models.notEmpty } }), ~c.models);
		~check.("unusable_model_labelled", ~v[\model].items.any { |i| i.contains("mock-legacy-0") and: { i.contains("unavailable") } },
			~v[\model].items);
		~choose.(\model, "mock-legacy-0");
		~check.("unusable_model_refused", ~kind.() == \unavailableModel and: { ~c.modelId != "mock-legacy-0" });
		~choose.(\model, "mock-composer-1");
		~check.("dj_selected", ~c.providerId == \mock and: { ~c.modelId == "mock-composer-1" }
			and: { ~v[\djIds].string.contains("mock-composer-1") }, ~v[\djIds].string);

		// Open the project.
		~v[\projectPath].string = ~root;
		~press.(\openProject);
		~check.("project_open", ~waitFor.({ ~c.project.notNil }) and: { ~c.projectFiles.includesEqual("main.scd") },
			~c.projectFiles);
		original = ~read.(~root +/+ "main.scd");
		before = ~snapshot.value;

		// Error path: the provider fails; nothing is written.
		~mockProvider.enqueue(MBError(\network, "mock outage: connection refused"));
		~v[\prompt].string = "Make a groove";
		~press.(\send);
		~waitFor.({ ~idle.value });
		~check.("provider_failure_shown", ~kind.() == \network and: { ~window.isShown(\errorRow) }
			and: { ~v[\conversation].string.contains("mock outage") } and: { ~c.proposal.isNil }, ~c.error);
		~check.("provider_failure_touches_nothing", ~snapshot.value == before);

		// Error path: the selected model disappears; requests are blocked, no fallback.
		~mockProvider.models = [MBMockProvider.defaultModels[1]];
		~press.(\refreshModels);
		~waitFor.({ ~c.modelRefreshing.not });
		~v[\prompt].string = "Make a groove";
		~press.(\send);
		~check.("unavailable_model_blocks", ~kind.() == \unavailableModel and: { ~c.modelId == "mock-composer-1" }
			and: { ~v[\model].items[~v[\model].value].contains("UNAVAILABLE") } and: { ~idle.value }, ~c.error);
		~check.("unavailable_model_touches_nothing", ~snapshot.value == before);
		~mockProvider.models = MBMockProvider.defaultModels;
		~press.(\refreshModels);
		~waitFor.({ ~c.modelRefreshing.not });
		~press.(\dismissError);

		// Propose with main.scd as context; review the diff; nothing written yet.
		~v[\contextFiles].selection = [~c.projectFiles.indexOfEqual("main.scd")];
		~v[\prompt].string = "Make a warm 120 BPM groove with a ChaosOsc lead";
		~press.(\send);
		~check.("proposal_arrived", ~waitFor.({ ~c.proposal.notNil or: { ~c.error.notNil } }, 60) and: { ~c.proposal.notNil },
			~c.error);
		proposal = ~c.proposal;
		~check.("proposal_valid_format", proposal.notNil and: { ~c.proposalState == \pending }
			and: { proposal[\edits].size == 1 } and: { proposal[\edits][0].path == "main.scd" }, proposal);
		~check.("diff_shown", ~v[\diff].string.contains("main.scd") and: { ~v[\diff].string.contains("ChaosOsc.ar") }
			and: { ~v[\plan].string.contains("Mock DJ sketch") });
		~check.("usage_shown", ~v[\usageLast].string.contains("mock / mock-composer-1")
			and: { ~v[\usageLast].string.contains("in ") }, ~v[\usageLast].string);
		~check.("nothing_written_before_approval", ~snapshot.value == before);

		// Approve -> confirm -> apply with backup.
		~press.(\approve);
		~check.("apply_needs_confirmation", ~window.isShown(\confirmPanel) and: { ~snapshot.value == before });
		~press.(\confirm);
		~check.("applied", ~waitFor.({ ~c.proposalState == \applied or: { ~c.error.notNil } }) and: { ~c.proposalState == \applied },
			~c.error);
		~check.("file_changed", ~read.(~root +/+ "main.scd") == proposal[\edits][0].newText);
		~check.("backup_saved", (~root +/+ ".maxxedbeats/backups/*").pathMatch.notEmpty);

		// Approve the render -> real NRT WAV with checks.
		~v[\duration].value = 2;
		~press.(\render);
		~check.("render_needs_confirmation", ~window.isShown(\confirmPanel) and: { ~c.busy.isNil });
		~press.(\confirm);
		~waitFor.({ ~idle.value }, 180);
		result = ~c.renderResult;
		~check.("render_succeeded", result.notNil and: { ~c.error.isNil }, ~c.error);
		if(result.notNil) {
			~check.("render_file", File.exists(result[\path]) and: { MBProject.comparablePath(result[\path]).beginsWith(MBProject.comparablePath(~c.project[\root]) ++ "/renders/") });
			~check.("render_checks", result[\checks][\ok] == true and: { result[\checks][\silent] == false }
				and: { result[\checks][\clipped] == false } and: { (result[\duration] - 2).abs < 0.01 }, result[\checks]);
			~check.("render_shown", ~v[\renderResult].string.contains(result[\path].basename)
				and: { ~v[\renderResult].string.contains("checks OK") } and: { ~v[\play].enabled });
			("MBTEST INFO wav=" ++ result[\path]).postln;
		};

		// Undo -> confirm -> original restored.
		~press.(\undo);
		~press.(\confirm);
		~waitFor.({ ~idle.value }, 30);
		~check.("undo_restored", ~read.(~root +/+ "main.scd") == original and: { ~c.error.isNil }, ~c.error);

		// Variation session: 2 candidates, approved renders, then a confirmed apply.
		~press.(\tabVariations);
		~v[\contextFiles].selection = [];
		~v[\varPrompt].string = "Darker and sparser";
		~v[\varMax].value = 2;
		~v[\varRender].value = true;
		~v[\duration].value = 2;
		~press.(\varStart);
		~check.("variation_render_needs_confirmation", ~window.isShown(\confirmPanel) and: { ~c.variation[\running].not });
		~press.(\confirm);
		~check.("variation_finished", ~waitFor.({ ~c.variation[\running].not }, 400) and: { ~c.error.isNil }, ~c.error);
		candidates = ~c.variation[\candidates];
		~check.("variation_two_candidates", candidates.size == 2 and: { ~v[\candidates].items.size == 2 }, candidates.size);
		~check.("variation_rendered_with_checks", candidates.every { |cand|
			cand[\status] == \rendered and: { cand[\render].notNil } and: { File.exists(cand[\render][\path]) }
			and: { cand[\checks][\ok] == true } }, candidates.collect { |cand| [cand[\status], cand[\error], cand[\checks]] });
		~check.("variation_candidates_differ", candidates.size == 2 and: { candidates[0][\seed] != candidates[1][\seed] }
			and: { candidates[0][\code].values.asArray != candidates[1][\code].values.asArray });
		~check.("variation_project_unchanged", ~read.(~root +/+ "main.scd") == original);
		~v[\candidates].value = 1;
		~press.(\applyCandidate);
		~check.("candidate_apply_needs_confirmation", ~window.isShown(\confirmPanel) and: { ~read.(~root +/+ "main.scd") == original });
		~press.(\confirm);
		~waitFor.({ ~idle.value }, 30);
		~check.("candidate_applied", ~c.error.isNil and: { ~read.(~root +/+ "main.scd") != original }
			and: { ~read.(~root +/+ "main.scd") == candidates[1][\code]["main.scd"] }, ~c.error);

		// Key management round trip with the fake store (no network).
		~press.(\tabKeys);
		secret = "sk-mbtest-" ++ "0123456789abcdefghijKLMNOP";
		~v[\keyField_openai].string = secret;
		~window.masks[\openai].sync;
		~press.(\keySave_openai);
		~check.("key_saved", ~waitFor.({ ~c.keyStatus[\openai] == \stored }) and: { ~store.keyPayload(\openai) == secret },
			~c.keyStatus[\openai]);
		~check.("key_never_shown", ~allText.value.contains("0123456789abcdefghij").not);
		~press.(\keyRemove_openai);
		~press.(\confirm);
		~check.("key_removed", ~waitFor.({ ~c.keyStatus[\openai] == \missing }) and: { ~store.keyPayload(\openai).isNil });
		~c.validateKey(\openai);
		~check.("validate_without_key_is_auth", ~waitFor.({ ~c.keyStatus[\openai] != \validating }) and: { ~kind.() == \auth });
		~press.(\tabCompose);
	} { |error|
		~check.("exception", false, error.errorString);
	};
	~window.close;
	~finish.value;
}.play(AppClock);
)
