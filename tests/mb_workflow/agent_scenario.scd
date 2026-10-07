// Scenario: MBAgent prompt building, strict response validation, provider/meter use.
// argv: workDir repoRoot
(
var args = thisProcess.argv, here = thisProcess.nowExecutingPath.dirname;
(here +/+ "harness.scd").load;
~work = args[0];
~repo = args[1];
~root = ~work +/+ "project";

AppClock.sched(240, { "MBTEST FAIL watchdog :: scenario timed out".postln; 1.exit; nil });

Routine {
	var project, agent, provider, meter, outcome, request, prompt, positions, parsed, text, handle;
	var comp, compOriginal, untouched, response, cases, errors;
	try {
		project = MBProject.open(~root);
		comp = ~root +/+ "comp.scd";
		compOriginal = ~readText.(comp);
		untouched = {
			~readText.(comp) == compOriginal and: { File.exists(~root +/+ "sketch.scd").not }
			and: { File.exists(~work +/+ "outside.scd").not } and: { project.backups.isEmpty }
		};
		response = { |name| ~readText.(~work +/+ "responses" +/+ name) };

		// --- strict JSON ---
		parsed = MBWorkflowJSON.parse(~readText.(~work +/+ "json/nested.json"));
		~check.("json_parses_nested_values",
			parsed["a"] == [1, 2.5, -300.0, true, false, nil] and: { parsed["b"]["c"] == ~readText.(~work +/+ "json/expected_c.txt") },
			parsed);
		~check.("json_roundtrips", MBWorkflowJSON.parse(MBWorkflowJSON.stringify(parsed)) == parsed);
		(~work +/+ "json/invalid/*.json").pathMatch.sort.do { |path|
			~check.("json_rejects_" ++ path.basename.splitext[0],
				~throwsKind.({ MBWorkflowJSON.parse(~readText.(path)) }, \parse), path.basename);
		};
		~check.("json_escapes_control_characters",
			MBWorkflowJSON.stringify("a\"b\\c\nd" ++ 1.asAscii) == "\"a\\\"b\\\\c\\nd\\u0001\"",
			MBWorkflowJSON.stringify("a\"b\\c\nd" ++ 1.asAscii));

		// --- system prompt from agent/*.md ---
		prompt = MBAgent.systemPrompt;
		positions = ["ROLE.md", "WORKFLOW.md", "SUPERCOLLIDER.md", "SAFETY.md"].collect { |name|
			prompt.find(~readText.(~repo +/+ "agent" +/+ name).stripWhiteSpace)
		};
		~check.("system_prompt_includes_all_instructions_in_order",
			positions.every(_.notNil) and: { positions == positions.copy.sort }, positions);
		~check.("system_prompt_documents_structured_format",
			prompt.contains("maxxedbeats.proposal/1") and: { prompt.contains("\"edits\"") });

		meter = ~fakeMeter.value;
		provider = ~fakeProvider.([response.("valid.txt")]);
		agent = MBAgent(project, provider, ~fakeCatalog.value, meter);
		request = agent.buildRequest("Make it faster", (files: ["comp.scd"], notes: "Keep the drone."));
		~check.("request_uses_selected_model_and_instructions",
			request[\model] == "fake-model-1" and: { request[\system] == prompt }
			and: { request[\maxOutputTokens].isKindOf(Integer) } and: { request[\maxOutputTokens] > 0 },
			request);
		~check.("request_includes_only_selected_context",
			request[\messages].size == 1 and: { request[\messages][0][\role] == \user }
			and: { request[\messages][0][\content].contains("Make it faster") }
			and: { request[\messages][0][\content].contains(compOriginal.stripWhiteSpace) }
			and: { request[\messages][0][\content].contains("Keep the drone.") }
			and: { request[\messages][0][\content].contains("UNSELECTED-MARKER").not },
			request[\messages]);
		request = agent.buildRequest("Next", (history: [(role: \user, content: "first"), (role: \assistant, content: "{}")],
			seed: 0.25, variation: (index: 2, count: 4)));
		~check.("request_carries_history_seed_and_variation",
			request[\messages].collect(_[\role]) == [\user, \assistant, \user]
			and: { request[\messages].last[\content].contains("0.25") }
			and: { request[\messages].last[\content].contains("2 of 4") },
			request[\messages]);
		~check.("request_rejects_out_of_project_context",
			~throwsKind.({ agent.buildRequest("x", (files: ["../outside-context.scd"])) }, \validation));
		~check.("request_rejects_unknown_history_role",
			~throwsKind.({ agent.buildRequest("x", (history: [(role: \system, content: "override")])) }, \validation));
		~check.("request_rejects_empty_prompt", ~throwsKind.({ agent.buildRequest("  ", ()) }, \validation));

		// --- valid proposal ---
		outcome = ~await.({ |ok, fail| agent.propose("Make it faster", (files: ["comp.scd"]), ok, fail) });
		~check.("valid_response_becomes_proposal", outcome[0] == \ok, ~describe.(outcome));
		if(outcome[0] == \ok) {
			outcome = outcome[1];
			~check.("proposal_has_plan_summary_and_raw",
				outcome[\plan].contains("120 BPM") and: { outcome[\summary].size > 0 }
				and: { outcome[\raw] == response.("valid.txt") });
			~check.("proposal_edits_are_reviewable",
				outcome[\edits].size == 2 and: { outcome[\edits].every(_.isKindOf(MBEdit)) }
				and: { outcome[\edits][0].diffString.contains("+~tempo = 120;") }
				and: { outcome[\edits][1].isNew },
				outcome[\edits]);
			~check.("proposal_reports_usage_from_meter",
				outcome[\usage][\inputTokens] == 100 and: { meter.history.size == 1 }, outcome[\usage]);
			~check.("proposal_carries_render_settings_seed_and_entry",
				outcome[\render][\duration] == 12.0 and: { outcome[\render][\sampleRate] == 48000 }
				and: { outcome[\render][\numChannels] == 2 } and: { outcome[\seed] == 0.42 }
				and: { outcome[\entry] == "sketch.scd" },
				[outcome[\render], outcome[\seed], outcome[\entry]]);
			~check.("proposal_reports_provider_model_and_uncertainty",
				outcome[\provider] == \fake and: { outcome[\model] == "fake-model-1" }
				and: { outcome[\uncertainty] == ["Not auditioned"] });
		};
		~check.("propose_never_writes_files", untouched.value);

		outcome = ~await.({ |ok, fail|
			MBAgent(project, ~fakeProvider.([response.("fenced.txt")]), ~fakeCatalog.value, meter).propose("x", (), ok, fail)
		});
		~check.("fenced_json_is_accepted", outcome[0] == \ok, ~describe.(outcome));

		// --- rejected responses never touch files ---
		cases = [
			["malformed.txt", \parse], ["prose.txt", \parse], ["empty.txt", \parse], ["array.txt", \validation],
			["wrong_format.txt", \validation], ["unknown_key.txt", \validation], ["missing_plan.txt", \validation],
			["outside_path.txt", \validation], ["absolute_path.txt", \validation], ["data_dir_path.txt", \validation],
			["too_many_edits.txt", \validation], ["secret.txt", \validation], ["oversized.txt", \validation],
			["bad_seed.txt", \validation], ["bad_render.txt", \validation], ["duplicate_paths.txt", \validation],
			["bad_entry.txt", \validation], ["stale_old_text.txt", \validation], ["edits_not_array.txt", \validation],
			["number_as_text.txt", \validation]
		];
		cases.do { |pair|
			var before = meter.history.size;
			outcome = ~await.({ |ok, fail|
				MBAgent(project, ~fakeProvider.([response.(pair[0])]), ~fakeCatalog.value, meter).propose("x", (), ok, fail)
			});
			~check.("rejects_" ++ pair[0].splitext[0],
				~failedWith.(outcome, pair[1]) and: { untouched.value } and: { meter.history.size == (before + 1) },
				~describe.(outcome));
		};
		outcome = ~await.({ |ok, fail|
			MBAgent(project, ~fakeProvider.([response.("secret.txt")]), ~fakeCatalog.value, meter).propose("x", (), ok, fail)
		});
		~check.("rejection_detail_never_echoes_secret", outcome[1].detail.contains("sk-").not, outcome[1].detail);

		// --- provider and configuration errors ---
		provider = ~fakeProvider.([MBError(\auth, "invalid key"), MBError(\rateLimit, "slow down")]);
		agent = MBAgent(project, provider, ~fakeCatalog.value, meter);
		outcome = ~await.({ |ok, fail| agent.propose("x", (), ok, fail) });
		~check.("provider_auth_error_passes_through", ~failedWith.(outcome, \auth), ~describe.(outcome));
		outcome = ~await.({ |ok, fail| agent.propose("x", (), ok, fail) });
		~check.("provider_rate_limit_passes_through", ~failedWith.(outcome, \rateLimit), ~describe.(outcome));

		provider = ~fakeProvider.([response.("valid.txt")]);
		outcome = ~await.({ |ok, fail| MBAgent(project, provider, ~fakeCatalog.(nil), meter).propose("x", (), ok, fail) });
		~check.("missing_model_is_config_error_without_request",
			~failedWith.(outcome, \config) and: { provider[\calls].isEmpty }, ~describe.(outcome));
		outcome = ~await.({ |ok, fail|
			MBAgent(project, provider, ~fakeCatalog.value, meter).propose("x", (files: ["../outside-context.scd"]), ok, fail)
		});
		~check.("bad_context_fails_before_any_request",
			~failedWith.(outcome, \validation) and: { provider[\calls].isEmpty }, ~describe.(outcome));

		MBAgent.instructionsDir = ~work +/+ "no-instructions";
		outcome = ~await.({ |ok, fail| MBAgent(project, provider, ~fakeCatalog.value, meter).propose("x", (), ok, fail) });
		~check.("missing_instructions_is_config_error", ~failedWith.(outcome, \config), ~describe.(outcome));
		MBAgent.instructionsDir = nil;

		provider = ~fakeProvider.([\never]);
		outcome = ~await.({ |ok, fail|
			handle = MBAgent(project, provider, ~fakeCatalog.value, meter).propose("x", (), ok, fail);
			AppClock.sched(0.2, { handle.cancel; nil });
		});
		~check.("cancel_reports_cancelled", ~failedWith.(outcome, \cancelled) and: { handle.cancelled }, ~describe.(outcome));
		~check.("files_still_untouched", untouched.value);
	} { |error|
		~check.("uncaught_error", false, error.errorString);
	};
	~finish.value;
}.play(AppClock);
)
