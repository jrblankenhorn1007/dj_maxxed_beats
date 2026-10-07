// Deterministic, offline fake services for the MaxxedBeats agent window.
// Evaluating this file returns a function; calling it returns an Event `f`:
//   f[\services]  the service port passed to MBGuiController (docs/design/gui.md)
//   f[\calls]     List of [op, args...] (never contains API keys)
//   f[\pending]   callbacks of "manual" operations, fired by the test/driver
//   f[\failures]  op -> error; the op fails with it instead of succeeding
// propose, render, startVariations, apply, and undo are manual: their
// callbacks wait in f[\pending][op] until the caller fires them.
{
	var f = (
		calls: List.new, pending: IdentityDictionary.new, failures: IdentityDictionary.new,
		keys: IdentityDictionary.new, selected: IdentityDictionary.new,
		models: IdentityDictionary.new, stale: IdentityDictionary.new,
		refreshed: IdentityDictionary.new, history: List.new,
		files: ["main.scd", "drums.scd", "notes.txt"], handles: List.new
	);
	var log = { |...args| f[\calls].add(args) };
	var failed = { |op, onFailure|
		var error = f[\failures][op];
		if(error.notNil) { onFailure.value(error); true } { false }
	};
	var handle = { |op|
		var h = (op: op, cancelled: false);
		h[\cancel] = { |self| self[\cancelled] = true; log.(\handleCancelled, op) };
		f[\handles].add(h);
		h
	};

	f[\models][\mock] = [
		(id: "mock-dj-1", displayName: "Mock DJ 1", provider: \mock, usable: true, note: ""),
		(id: "mock-dj-retired", displayName: "Retired DJ", provider: \mock, usable: false,
			note: "retired by provider")
	];
	f[\models][\openai] = [
		(id: "gpt-test-1", displayName: "GPT Test 1", provider: \openai, usable: true, note: "")
	];
	f[\models][\anthropic] = [];
	f[\refreshed][\mock] = "2026-10-06 21:00";
	f[\selected][\mock] = "mock-dj-1";
	f[\refreshResult] = IdentityDictionary.new;

	f[\usage] = (provider: \mock, model: "mock-dj-1", inputTokens: 120, outputTokens: 45,
		cachedInputTokens: 0, usd: 0.0123, credits: 1.23, rateStatus: \ok,
		rateTable: "mock-rates-2026-10");
	f[\proposal] = {
		(
			plan: "Plan: 8-bar intro, 16-bar groove at 120 BPM; ChaosOsc lead.",
			summary: "Adds a four-on-the-floor kick to main.scd.",
			edits: [
				(path: "main.scd", oldText: "// kick\n", newText: "~kick = 1;\n", isNew: false,
					diffString: "--- a/main.scd\n+++ b/main.scd\n-// kick\n+~kick = 1;\n")
			],
			usage: f[\usage].copy,
			raw: "{}"
		)
	};
	f[\renderResult] = { |checks|
		(path: "/fake/project/renders/main-20261006-001.wav",
			metadataPath: "/fake/project/renders/main-20261006-001.json",
			duration: 4.0, sampleRate: 48000, numChannels: 2,
			checks: checks ? (finite: true, silent: false, clipped: false, durationOk: true))
	};
	f[\candidate] = { |i|
		(index: i, seed: 1000 + i, summary: "Variation " ++ (i + 1),
			render: (path: "/fake/project/.maxxedbeats/sessions/s1/cand" ++ i ++ ".wav",
				checks: (finite: true, silent: false, clipped: false, durationOk: true)))
	};

	f[\services] = (
		providers: {
			log.(\providers);
			[
				(id: \openai, displayName: "OpenAI", requiresKey: true),
				(id: \anthropic, displayName: "Anthropic", requiresKey: true),
				(id: \mock, displayName: "Mock DJ", requiresKey: false)
			]
		},
		hasKey: { |id, onResult| log.(\hasKey, id); onResult.value(f[\keys][id].notNil) },
		storeKey: { |id, key, onSuccess, onFailure|
			log.(\storeKey, id);
			if(failed.(\storeKey, onFailure).not) { f[\keys][id] = key; onSuccess.value(true) }
		},
		removeKey: { |id, onSuccess, onFailure|
			log.(\removeKey, id);
			if(failed.(\removeKey, onFailure).not) { f[\keys].removeAt(id); onSuccess.value(true) }
		},
		validateKey: { |id, onSuccess, onFailure|
			log.(\validateKey, id);
			if(failed.(\validateKey, onFailure).not) { onSuccess.value(true) }
		},
		refreshModels: { |id, onSuccess, onFailure|
			log.(\refreshModels, id);
			if(failed.(\refreshModels, onFailure).not) {
				f[\refreshResult][id] !? { |models| f[\models][id] = models };
				f[\refreshed][id] = "2026-10-06 21:30";
				f[\stale][id] = false;
				onSuccess.value(f[\models][id])
			} {
				f[\stale][id] = true;
			}
		},
		models: { |id| f[\models][id] ? [] },
		lastRefreshed: { |id| f[\refreshed][id] },
		isStale: { |id| f[\stale][id] ? false },
		selectedModel: { |id| f[\selected][id] },
		selectModel: { |id, modelId| log.(\selectModel, id, modelId); f[\selected][id] = modelId },
		sessionTotals: {
			var records = f[\history];
			if(records.isEmpty) { nil } {
				(requests: records.size,
					inputTokens: records.sum { |r| r[\inputTokens] },
					outputTokens: records.sum { |r| r[\outputTokens] },
					cachedInputTokens: records.sum { |r| r[\cachedInputTokens] },
					usd: if(records.every { |r| r[\usd].notNil }) { records.sum { |r| r[\usd] } },
					credits: if(records.every { |r| r[\credits].notNil }) { records.sum { |r| r[\credits] } },
					rateStatus: if(records.every { |r| r[\rateStatus] == \ok }) { \ok } { \missing },
					rateTable: "mock-rates-2026-10")
			}
		},
		history: { f[\history].asArray },
		clearHistory: { log.(\clearHistory); f[\history].clear },
		openProject: { |dir, onSuccess, onFailure|
			log.(\openProject, dir);
			if(failed.(\openProject, onFailure).not) {
				onSuccess.value((root: dir, files: f[\files].copy, project: (fakeProject: dir)))
			}
		},
		projectFiles: { |project| f[\files].copy },
		propose: { |project, providerId, modelId, prompt, context, onSuccess, onFailure|
			log.(\propose, providerId, modelId, prompt, context);
			f[\pending][\propose] = [onSuccess, onFailure];
			handle.(\propose)
		},
		apply: { |project, proposal, confirmed, onSuccess, onFailure|
			log.(\apply, confirmed);
			f[\pending][\apply] = [onSuccess, onFailure];
			handle.(\apply)
		},
		undo: { |project, onSuccess, onFailure|
			log.(\undo);
			f[\pending][\undo] = [onSuccess, onFailure];
			handle.(\undo)
		},
		render: { |project, entryPath, settings, approved, onProgress, onSuccess, onFailure|
			log.(\render, entryPath, settings, approved);
			f[\pending][\render] = [onSuccess, onFailure, onProgress];
			handle.(\render)
		},
		startVariations: { |project, providerId, modelId, prompt, maxCandidates, approveRenders, settings, context,
			onCandidate, onDone, onFailure|
			log.(\startVariations, providerId, modelId, prompt, maxCandidates, approveRenders, settings, context);
			f[\pending][\variations] = [onCandidate, onDone, onFailure];
			(session: 1)
		},
		renderCandidate: { |session, index, onProgress, onSuccess, onFailure|
			log.(\renderCandidate, index);
			f[\pending][\renderCandidate] = [onSuccess, onFailure, onProgress];
			handle.(\renderCandidate)
		},
		stopVariations: { |session| log.(\stopVariations) },
		applyVariation: { |session, index, confirmed, onSuccess, onFailure|
			log.(\applyVariation, index, confirmed);
			f[\pending][\applyVariation] = [onSuccess, onFailure];
			handle.(\applyVariation)
		},
		cancel: { |h| log.(\cancel, h !? { h[\op] }); h !? { h.cancel } },
		play: { |path, onStarted, onDone, onFailure|
			log.(\play, path);
			if(failed.(\play, onFailure).not) {
				f[\pending][\playDone] = onDone;
				onStarted.value;
			};
			(playing: path)
		},
		stopPlayback: { |h| log.(\stopPlayback) },
		reveal: { |path| log.(\reveal, path) }
	);

	// Helpers used by tests and the visual driver.
	f[\callsOf] = { |self, op| self[\calls].select { |c| c[0] == op } };
	f[\fire] = { |self, op, which = 0 ...args|
		var callbacks = self[\pending][op];
		if(callbacks.isNil) { MBError(\validation, "no pending " ++ op).throw };
		if(which < 2 and: { op != \variations }) { self[\pending].removeAt(op) };
		callbacks[which].valueArray(args)
	};
	f[\succeedPropose] = { |self, proposal|
		proposal = proposal ?? { self[\proposal].value };
		if(proposal[\usage].notNil) { self[\history].add(proposal[\usage]) };
		self.fire(\propose, 0, proposal)
	};
	f
}
