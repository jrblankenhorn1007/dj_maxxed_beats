// Shared helpers for headless MaxxedBeats workflow scenarios.
// Loaded by each scenario; prints MBTEST lines parsed by harness.py.
~mbtFailures = 0;

~check = { |name, condition, detail = ""|
	if(condition == true) {
		("MBTEST PASS " ++ name).postln;
	} {
		~mbtFailures = ~mbtFailures + 1;
		("MBTEST FAIL " ++ name ++ " :: " ++ detail.asString.replace("\n", " ")).postln;
	};
	condition == true
};

~finish = {
	("MBTEST DONE failures=" ++ ~mbtFailures).postln;
	AppClock.sched(0.1, { 0.exit; nil });
};

// Inside a Routine: calls fn with (onSuccess, onFailure) and waits for one.
// Returns [\ok, value] or [\fail, error] (or [\timeout, nil]).
~await = { |fn, timeout = 30|
	var condition = Condition(false), outcome, timer;
	timer = AppClock.sched(timeout, {
		if(outcome.isNil) { outcome = [\timeout, nil]; condition.test = true; condition.signal };
		nil
	});
	fn.value(
		{ |value| if(outcome.isNil) { outcome = [\ok, value]; condition.test = true; condition.signal } },
		{ |error| if(outcome.isNil) { outcome = [\fail, error]; condition.test = true; condition.signal } }
	);
	condition.wait;
	outcome
};

~failedWith = { |outcome, kind|
	outcome[0] == \fail and: { outcome[1].isKindOf(MBError) } and: { outcome[1].kind == kind }
};

~describe = { |outcome|
	if(outcome[1].isKindOf(Error)) {
		outcome[0].asString ++ " " ++ outcome[1].errorString
	} {
		outcome[0].asString ++ " " ++ outcome[1].asString.keep(400)
	}
};

~throwsKind = { |fn, kind|
	var caught = MBWorkflowTry.value({ fn.value; nil });
	caught.isKindOf(MBError) and: { caught.kind == kind }
};

~writeText = { |path, text|
	File.mkdir(path.dirname);
	File.use(path, "wb", { |file| file.write(text) });
};

~readText = { |path|
	if(File.exists(path)) { File.use(path, "rb", { |file| file.readAllString }) } { nil }
};

// Deterministic, offline duck-typed collaborators (no worker-01 classes).
~fakeProvider = { |responses, delay = 0.0|
	var queue = List.newFrom(responses), calls = List.new;
	(
		id: \fake,
		displayName: "Fake DJ",
		calls: calls,
		complete: { |self, request, onSuccess, onFailure|
			var next = queue.removeAt(0), cancelled = false;
			calls.add(request);
			AppClock.sched(delay, {
				if(cancelled.not) {
					if(next.isKindOf(Error)) {
						onFailure.value(next)
					} {
						if(next == \never) { nil } {
							onSuccess.value((
								provider: \fake,
								model: request[\model],
								text: next.value(request),
								usage: (inputTokens: 100, outputTokens: 50, cachedInputTokens: 0),
								requestId: "req-" ++ calls.size
							))
						}
					}
				};
				nil
			});
			(cancel: { |handle| cancelled = true })
		}
	)
};

~fakeCatalog = { |model = "fake-model-1"|
	(selectedModel: { |self, providerId| model })
};

~fakeMeter = {
	var history = List.new;
	(
		history: history,
		record: { |self, response|
			var entry = (
				provider: response[\provider],
				model: response[\model],
				inputTokens: response[\usage] !? { |u| u[\inputTokens] },
				outputTokens: response[\usage] !? { |u| u[\outputTokens] },
				cachedInputTokens: 0,
				usd: nil,
				credits: nil,
				rateStatus: \missing,
				rateTable: "test"
			);
			history.add(entry);
			entry
		}
	)
};

// Builds a structured proposal response string.
~proposalJSON = { |edits, extra|
	var object = (
		format: "maxxedbeats.proposal/1",
		plan: "Sections: intro and pulse. Tempo 120 BPM. ChaosOsc drone.",
		summary: "Adds a short ChaosOsc sketch.",
		assumptions: ["Stereo output"],
		uncertainty: ["Not auditioned"],
		edits: edits
	);
	extra !? { extra.keysValuesDo { |key, value| object.put(key, value) } };
	MBWorkflowJSON.stringify(object)
};
