// Scenario: approved headless render (separate sclang + scsynth NRT with ChaosOsc), checks, errors.
// argv: workDir repoRoot pluginDir sclang scsynth
(
var args = thisProcess.argv, here = thisProcess.nowExecutingPath.dirname;
(here +/+ "harness.scd").load;
~work = args[0];
~pluginDir = args[2];
~sclang = args[3];
~scsynth = args[4];
~root = ~work +/+ "project";

AppClock.sched(420, { "MBTEST FAIL watchdog :: scenario timed out".postln; 1.exit; nil });

~settings = { |extra|
	var settings = (duration: 3.0, sampleRate: 48000, numChannels: 2, pluginPaths: [~pluginDir],
		sclang: ~sclang, scsynth: ~scsynth, timeout: 60);
	extra !? { settings.putAll(extra) };
	settings
};
~render = { |project, entry, extra, approved = true, progress|
	~await.({ |ok, fail|
		MBRenderer.render(project, entry, ~settings.(extra), approved, { |event| progress !? { progress.add(event) } }, ok, fail)
	}, 120)
};
~wavs = { (~root +/+ "renders/*.wav").pathMatch };
~sidecars = { (~root +/+ "renders/*.json").pathMatch };

Routine {
	var project, agent, outcome, proposal, result, first, metadata, progress, before, handle, secret;
	try {
		project = MBProject.open(~root);
		"MB_RENDER_TEST_PARENT_ONLY".setenv("parent-environment-value");

		outcome = ~render.(project, "comp.scd", nil, false);
		~check.("render_requires_approval", ~failedWith.(outcome, \validation), ~describe.(outcome));
		outcome = ~render.(project, "comp.scd", nil, "yes");
		~check.("render_requires_boolean_approval", ~failedWith.(outcome, \validation), ~describe.(outcome));
		~check.("unapproved_render_creates_nothing",
			File.exists(~root +/+ "renders").not and: { File.exists(project.dataDir).not });

		// End to end: propose (fake provider) -> confirmed apply -> approved render -> checks.
		agent = MBAgent(project, ~fakeProvider.([~readText.(~work +/+ "proposal.txt")]), ~fakeCatalog.value, ~fakeMeter.value);
		outcome = ~await.({ |ok, fail| agent.propose("Make a ChaosOsc drone", (files: ["comp.scd"]), ok, fail) });
		~check.("e2e_propose", outcome[0] == \ok, ~describe.(outcome));
		proposal = outcome[1];
		outcome = ~await.({ |ok, fail| project.apply(proposal, true, ok, fail) });
		~check.("e2e_confirmed_apply", outcome[0] == \ok, ~describe.(outcome));
		progress = List.new;
		outcome = ~render.(project, proposal[\entry],
			(duration: proposal[\render][\duration], seed: proposal[\seed],
				metadata: (summary: proposal[\summary], prompt: proposal[\prompt], provider: proposal[\provider],
					model: proposal[\model], apiKey: "should-not-be-copied")),
			true, progress);
		~check.("e2e_render_succeeds", outcome[0] == \ok, ~describe.(outcome));
		result = outcome[1];
		if(outcome[0] == \ok) {
			~check.("e2e_output_in_project_renders",
				result[\path].beginsWith(project.root +/+ "renders/") and: { result[\path].endsWith(".wav") }
				and: { File.exists(result[\path]) }, result[\path]);
			~check.("e2e_output_matches_settings",
				(result[\duration] - 3.0).abs < 0.01 and: { result[\sampleRate] == 48000 } and: { result[\numChannels] == 2 },
				[result[\duration], result[\sampleRate], result[\numChannels]]);
			~check.("e2e_checks_pass",
				result[\checks][\finite] == true and: { result[\checks][\silent] == false }
				and: { result[\checks][\clipped] == false } and: { result[\checks][\durationOk] == true }
				and: { result[\checks][\ok] == true },
				result[\checks]);
			metadata = MBWorkflowJSON.parse(~readText.(result[\metadataPath]));
			~check.("e2e_metadata_sidecar",
				result[\metadataPath] == (result[\path].splitext[0] ++ ".json")
				and: { metadata["status"] == "rendered" } and: { metadata["seed"] == 0.42 }
				and: { metadata["entry"] == "sketch.scd" } and: { metadata["provider"] == "fake" }
				and: { metadata["model"] == "fake-model-1" } and: { metadata["settings"]["sampleRate"] == 48000 }
				and: { metadata["checks"]["ok"] == true } and: { metadata["summary"].size > 0 },
				metadata);
			~check.("e2e_metadata_has_no_secrets_or_unknown_fields",
				~readText.(result[\metadataPath]).contains("should-not-be-copied").not
				and: { ~readText.(result[\metadataPath]).contains("sk-").not });
			~check.("e2e_progress_reported",
				[\building, \rendering, \checking, \done].every { |stage| progress.any { |event| event[\stage] == stage } }
				and: { progress.last[\fraction] == 1.0 },
				progress.collect(_[\stage]));
			~check.("generated_code_not_evaluated_in_user_interpreter", ~leak.isNil, ~leak);
			first = result;
			outcome = ~render.(project, "sketch.scd", (seed: 0.42));
			~check.("second_render_gets_unique_name",
				outcome[0] == \ok and: { outcome[1][\path] != first[\path] } and: { File.exists(first[\path]) }
				and: { ~wavs.value.size == 2 } and: { ~sidecars.value.size == 2 },
				~describe.(outcome));
		};

		outcome = ~render.(project, "classic.scd", (duration: 4.0, sampleFormat: "int24"));
		~check.("child_has_quark_and_chaososc_classes_and_isolated_env",
			outcome[0] == \ok and: { outcome[1][\checks][\ok] }, ~describe.(outcome));

		before = [~wavs.value.size, ~sidecars.value.size];
		[
			["broken.scd", "syntax"], ["runtime.scd", "mbUndefinedMethod"], ["notscore.scd", "Score"],
			["badevents.scd", "Score"]
		].do { |pair|
			outcome = ~render.(project, pair[0]);
			~check.("build_failure_" ++ pair[0].splitext[0],
				~failedWith.(outcome, \render) and: { outcome[1].detail.contains(pair[1]) }
				and: { outcome[1].detail.contains("log") },
				~describe.(outcome));
		};
		~check.("failed_renders_leave_no_outputs", [~wavs.value.size, ~sidecars.value.size] == before,
			[~wavs.value, ~sidecars.value]);

		outcome = ~render.(project, "hang.scd", (timeout: 4));
		~check.("hung_composition_times_out", ~failedWith.(outcome, \render) and: { outcome[1].detail.contains("timed out") },
			~describe.(outcome));

		outcome = ~render.(project, "sketch.scd", (pluginPaths: [~work +/+ "empty-plugins"]));
		~check.("missing_chaososc_plugin_is_actionable",
			~failedWith.(outcome, \render) and: { outcome[1].detail.contains("ChaosOsc") }
			and: { outcome[1].detail.contains("plugin") },
			~describe.(outcome));

		outcome = ~render.(project, "silent.scd");
		~check.("silent_render_is_flagged",
			outcome[0] == \ok and: { outcome[1][\checks][\silent] } and: { outcome[1][\checks][\ok].not },
			~describe.(outcome));
		outcome = ~render.(project, "clip.scd", (numChannels: 1, sampleRate: 44100, duration: 2.0));
		~check.("clipping_render_is_flagged_and_format_matches",
			outcome[0] == \ok and: { outcome[1][\checks][\clipped] } and: { outcome[1][\numChannels] == 1 }
			and: { outcome[1][\sampleRate] == 44100 } and: { (outcome[1][\duration] - 2.0).abs < 0.01 },
			~describe.(outcome));

		[
			["../outside.scd", nil, \validation], ["notes.md", nil, \validation], ["missing.scd", nil, \io],
			["comp.scd", (duration: 0), \validation], ["comp.scd", (sampleRate: 1234), \validation],
			["comp.scd", (sampleFormat: "mp3"), \validation], ["comp.scd", (sclang: ~work +/+ "no-sclang"), \config],
			["comp.scd", (seed: 1.5), \validation]
		].do { |triple, index|
			outcome = ~render.(project, triple[0], triple[1]);
			~check.("invalid_request_" ++ index, ~failedWith.(outcome, triple[2]), ~describe.(outcome));
		};

		before = [~wavs.value.size, ~sidecars.value.size];
		outcome = ~await.({ |ok, fail|
			handle = MBRenderer.render(project, "comp.scd", ~settings.value, true, nil, ok, fail);
			AppClock.sched(0.3, { handle.cancel; nil });
		}, 60);
		~check.("cancel_stops_render_without_outputs",
			~failedWith.(outcome, \cancelled) and: { [~wavs.value.size, ~sidecars.value.size] == before },
			~describe.(outcome));
	} { |error|
		~check.("uncaught_error", false, error.errorString);
	};
	~finish.value;
}.play(AppClock);
)
