// Scenario: user-started, bounded variation (sampling) sessions with isolated candidates.
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

~responses = { |names| names.collect { |name| ~readText.(~work +/+ "responses" +/+ name ++ ".txt") } };
~agent = { |project, responses, delay = 0.0|
	var provider = ~fakeProvider.(responses, delay);
	[MBAgent(project, provider, ~fakeCatalog.value, ~fakeMeter.value), provider]
};
// Runs a session to completion; returns (done:, failure:, seen:).
~runSession = { |session, prompt, approveRenders = false, onEach|
	var seen = List.new, outcome;
	outcome = ~await.({ |ok, fail|
		session.start(prompt,
			{ |candidate| seen.add(candidate); onEach !? { onEach.value(candidate, session) } },
			{ |candidates, stopped| ok.value((candidates: candidates, stopped: stopped)) },
			{ |error| fail.value(error) },
			approveRenders)
	}, 180);
	(outcome: outcome, seen: seen)
};

Routine {
	var project, original, pair, session, run, candidates, outcome, sessionDir, contents, again;
	try {
		project = MBProject.open(~root);
		original = ~readText.(~root +/+ "comp.scd");

		pair = ~agent.(project, ~responses.(["var1", "var2", "var3", "var4", "var5", "var6"]));
		session = MBVariationSession(pair[0], project, context: (files: ["comp.scd"], entry: "comp.scd"));
		~check.("default_cap_is_four", session.maxCandidates == 4, session.maxCandidates);
		~check.("seeds_are_fixed_and_deterministic",
			session.seeds == MBVariationSession.defaultSeeds(4)
			and: { MBVariationSession(pair[0], project).seeds == session.seeds }
			and: { session.seeds.asSet.size == 4 } and: { session.seeds.every { |seed| seed > 0 and: { seed < 1 } } },
			session.seeds);
		~check.("nothing_runs_before_user_starts",
			session.state == \idle and: { session.candidates.isEmpty } and: { pair[1][\calls].isEmpty }
			and: { File.exists(project.sessionsDir).not });

		run = ~runSession.(session, "Explore darker drones");
		~check.("session_completes", run[\outcome][0] == \ok and: { run[\outcome][1][\stopped] == false }, ~describe.(run[\outcome]));
		candidates = session.candidates;
		~check.("session_stops_at_cap",
			candidates.size == 4 and: { run[\seen].size == 4 } and: { pair[1][\calls].size == 4 }
			and: { session.state == \done },
			[candidates.size, pair[1][\calls].size]);
		~check.("each_request_uses_its_fixed_seed",
			pair[1][\calls].collect { |request, index|
				request[\messages].last[\content].contains(session.seeds[index].asString)
				and: { request[\messages].last[\content].contains((index + 1).asString ++ " of 4") }
			}.every(_ == true));
		~check.("candidates_keep_code_seed_settings_and_isolated_workspace",
			candidates.every { |candidate, index|
				candidate[\status] == \proposed and: { candidate[\seed] == session.seeds[index] }
				and: { candidate[\index] == index }
				and: { MBProject.comparablePath(candidate[\dir]).beginsWith(MBProject.comparablePath(project.sessionsDir +/+ session.id) ++ "/") }
				and: { candidate[\code]["comp.scd"].contains("Variation " ++ (index + 1)) }
				and: { ~readText.(candidate[\project].root +/+ "comp.scd").contains("Variation " ++ (index + 1)) }
				and: { candidate[\settings][\duration] == 2.0 } and: { candidate[\entry] == "comp.scd" }
				and: { candidate[\diff].contains("+// Variation " ++ (index + 1)) }
				and: { File.exists(candidate[\dir] +/+ "candidate.json") }
				and: { candidate[\render].isNil }
			},
			candidates.collect { |c| [c[\status], c[\seed], c[\entry], c[\settings]] });
		~check.("original_project_untouched_by_session",
			~readText.(~root +/+ "comp.scd") == original and: { project.backups.isEmpty }
			and: { File.exists(~root +/+ "renders").not });
		sessionDir = project.sessionsDir +/+ session.id;
		contents = MBWorkflowJSON.parse(~readText.(sessionDir +/+ "session.json"));
		~check.("session_record_written",
			contents["state"] == "done" and: { contents["candidates"].size == 4 } and: { contents["maxCandidates"] == 4 },
			contents);

		outcome = ~await.({ |ok, fail| session.start("again", nil, ok, fail) });
		~check.("session_cannot_restart", ~failedWith.(outcome, \validation), ~describe.(outcome));

		outcome = ~await.({ |ok, fail| session.renderCandidate(0, false, nil, ok, fail) });
		~check.("candidate_render_requires_approval", ~failedWith.(outcome, \validation), ~describe.(outcome));
		outcome = ~await.({ |ok, fail|
			session.renderCandidate(0, true, nil, ok, fail, (pluginPaths: [~pluginDir], sclang: ~sclang, scsynth: ~scsynth))
		}, 120);
		~check.("candidate_render_on_request",
			outcome[0] == \ok and: { session.candidates[0][\status] == \rendered }
			and: { session.candidates[0][\render][\path].beginsWith(session.candidates[0][\dir]) }
			and: { session.candidates[0][\checks][\ok] } and: { File.exists(~root +/+ "renders").not },
			~describe.(outcome));

		outcome = ~await.({ |ok, fail| session.apply(1, false, ok, fail) });
		~check.("apply_candidate_requires_confirmation",
			~failedWith.(outcome, \validation) and: { ~readText.(~root +/+ "comp.scd") == original }, ~describe.(outcome));
		outcome = ~await.({ |ok, fail| session.apply(9, true, ok, fail) });
		~check.("apply_unknown_candidate_rejected", ~failedWith.(outcome, \validation), ~describe.(outcome));
		outcome = ~await.({ |ok, fail| session.apply(1, true, ok, fail) });
		~check.("confirmed_apply_copies_selected_candidate",
			outcome[0] == \ok and: { ~readText.(~root +/+ "comp.scd") == session.candidates[1][\code]["comp.scd"] }
			and: { project.backups.size == 1 },
			~describe.(outcome));
		outcome = ~await.({ |ok, fail| project.undo(ok, fail) });
		~check.("applied_candidate_can_be_undone", outcome[0] == \ok and: { ~readText.(~root +/+ "comp.scd") == original });

		// Approved rendering of a smaller session.
		pair = ~agent.(project, ~responses.(["var1", "var2", "var3"]));
		session = MBVariationSession(pair[0], project, 2,
			(duration: 2.0, pluginPaths: [~pluginDir], sclang: ~sclang, scsynth: ~scsynth),
			(files: ["comp.scd"], entry: "comp.scd"));
		run = ~runSession.(session, "Two rendered variants", true);
		~check.("rendered_session_completes", run[\outcome][0] == \ok, ~describe.(run[\outcome]));
		~check.("rendered_candidates_have_audio_and_checks",
			session.candidates.size == 2 and: { pair[1][\calls].size == 2 }
			and: { session.candidates.every { |candidate|
				candidate[\status] == \rendered and: { File.exists(candidate[\render][\path]) }
				and: { candidate[\render][\path].beginsWith(candidate[\dir]) }
				and: { candidate[\checks][\ok] } and: { (candidate[\render][\duration] - 2.0).abs < 0.01 }
				and: { MBWorkflowJSON.parse(~readText.(candidate[\render][\metadataPath]))["sessionId"] == session.id }
			} },
			session.candidates.collect { |c| [c[\status], c[\error] !? { |e| e.errorString }] });
		~check.("rendered_session_keeps_original_untouched",
			~readText.(~root +/+ "comp.scd") == original and: { File.exists(~root +/+ "renders").not });

		// Stop early from the first candidate callback.
		pair = ~agent.(project, ~responses.(["var1", "var2", "var3", "var4"]), 0.2);
		session = MBVariationSession(pair[0], project, 4, nil, (files: ["comp.scd"]));
		run = ~runSession.(session, "Stop after one", false, { |candidate, owner| owner.stop });
		~check.("stop_early_ends_session",
			run[\outcome][0] == \ok and: { run[\outcome][1][\stopped] == true } and: { session.state == \stopped }
			and: { session.candidates.size == 1 } and: { pair[1][\calls].size == 1 },
			[~describe.(run[\outcome]), session.candidates.size, pair[1][\calls].size]);
		session.stop;
		~check.("stop_is_idempotent", session.state == \stopped);

		// Stop while a request is in flight.
		pair = ~agent.(project, ~responses.(["var1"]) ++ [\never]);
		session = MBVariationSession(pair[0], project, 3, nil, (files: ["comp.scd"]));
		outcome = ~await.({ |ok, fail|
			session.start("in flight", { |candidate| AppClock.sched(0.2, { session.stop; nil }) },
				{ |candidates, stopped| ok.value([candidates.size, stopped]) }, fail)
		});
		~check.("stop_cancels_in_flight_request", outcome[0] == \ok and: { outcome[1] == [1, true] }, ~describe.(outcome));

		// A malformed candidate counts toward the cap; the session continues.
		pair = ~agent.(project, ~responses.(["malformed", "var2", "var3"]));
		session = MBVariationSession(pair[0], project, 2, nil, (files: ["comp.scd"]));
		run = ~runSession.(session, "One bad answer");
		~check.("bad_candidate_is_recorded_and_counted",
			run[\outcome][0] == \ok and: { session.candidates.size == 2 }
			and: { session.candidates[0][\status] == \failed } and: { session.candidates[0][\error].kind == \parse }
			and: { session.candidates[1][\status] == \proposed } and: { pair[1][\calls].size == 2 },
			session.candidates.collect(_[\status]));
		outcome = ~await.({ |ok, fail| session.apply(0, true, ok, fail) });
		~check.("failed_candidate_cannot_be_applied", ~failedWith.(outcome, \validation), ~describe.(outcome));

		// Provider errors end the session.
		pair = ~agent.(project, [MBError(\auth, "invalid key")] ++ ~responses.(["var2"]));
		session = MBVariationSession(pair[0], project, 3, nil, (files: ["comp.scd"]));
		run = ~runSession.(session, "Auth fails");
		~check.("provider_error_ends_session",
			~failedWith.(run[\outcome], \auth) and: { session.state == \failed } and: { pair[1][\calls].size == 1 },
			~describe.(run[\outcome]));

		~check.("cap_is_bounded", MBVariationSession(pair[0], project, 1000).maxCandidates == MBVariationSession.hardLimit
			and: { MBVariationSession(pair[0], project, 0).maxCandidates == 1 });
		~check.("original_still_untouched", ~readText.(~root +/+ "comp.scd") == original);
	} { |error|
		~check.("uncaught_error", false, error.errorString);
	};
	~finish.value;
}.play(AppClock);
)
