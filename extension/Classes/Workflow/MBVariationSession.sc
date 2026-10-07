/*
The in-app music exploration ("sampling") loop.

Runs only after the user calls .start, proposes at most maxCandidates
(default 4, hard limit 16) variations one at a time with fixed seeds, and
stops at the cap, on .stop, or on a provider error. Each candidate lives in
<project>/.maxxedbeats/sessions/<id>/candidate-NN/ with a copy of the
project, its code, seed, settings, render, and checks; the original project
is changed only by a confirmed .apply. Candidates are rendered only when the
user approved rendering (start(..., approveRenders: true) or
.renderCandidate(index, true, ...)).
*/
MBVariationSession {
	classvar <>hardLimit = 16, <>maxCopyBytes = 67108864;
	var <agent, <project, <maxCandidates, <>renderSettings, <>context, <>seeds;
	var <candidates, <id, <dir, <state = \idle, <prompt;
	var onCandidate, onDone, onFailure, approveRenders = false, current, doneCalled = false;

	*new { |agent, project, maxCandidates = 4, renderSettings, context|
		^super.newCopyArgs(agent, project).initSession(maxCandidates, renderSettings, context)
	}

	*defaultSeeds { |count|
		^count.collect { |index| (((index + 1) * 0.6180339887498949) % 1.0).round(0.0001).clip(0.01, 0.99) }
	}

	initSession { |argMax, argSettings, argContext|
		maxCandidates = (argMax ? 4).asInteger.clip(1, hardLimit);
		renderSettings = argSettings;
		context = argContext ? ();
		seeds = MBVariationSession.defaultSeeds(maxCandidates);
		candidates = List.new;
	}

	isRunning { ^state == \running }

	start { |argPrompt, argOnCandidate, argOnDone, argOnFailure, argApproveRenders = false|
		var problem;
		problem = case
		{ state != \idle } { "this sampling session was already started; create a new session to sample again" }
		{ argPrompt.isString.not or: { argPrompt.stripWhiteSpace.isEmpty } } { "describe the variations to explore" }
		{ seeds.size < maxCandidates or: { seeds.any { |seed| seed.isKindOf(SimpleNumber).not or: { seed <= 0 } or: { seed >= 1 } } } } {
			"provide one seed strictly between 0 and 1 per candidate"
		};
		if(problem.notNil) {
			AppClock.sched(0, { argOnFailure.value(MBError(\validation, problem)); nil });
			^this
		};
		prompt = argPrompt;
		onCandidate = argOnCandidate;
		onDone = argOnDone;
		onFailure = argOnFailure;
		approveRenders = argApproveRenders === true;
		id = "session-" ++ Date.getDate.format("%Y%m%d-%H%M%S") ++ "-" ++ 1000000.rand.asStringToBase(10, 6);
		dir = project.sessionsDir +/+ id;
		File.mkdir(dir);
		state = \running;
		this.prWriteSession;
		this.prNext(0);
	}

	stop {
		if(state == \running) {
			state = \stopped;
			current !? { current.cancel };
			current = nil;
			candidates.do { |candidate| if(candidate[\status] == \rendering) { candidate[\status] = \proposed } };
			this.prDone;
		};
	}

	apply { |index, confirmed = false, onSuccess, onFailure|
		var candidate = this.prCandidateFor(index, onFailure);
		if(candidate.notNil) { project.apply(candidate[\proposal], confirmed, onSuccess, onFailure) };
	}

	renderCandidate { |index, approved = false, onProgress, onSuccess, onFailure, overrides|
		var candidate = this.prCandidateFor(index, onFailure), settings;
		if(candidate.isNil) { ^nil };
		settings = candidate[\settings].copy;
		overrides !? { settings.putAll(overrides) };
		candidate[\status] = \rendering;
		^MBRenderer.render(candidate[\project], candidate[\entry], settings, approved, onProgress,
			{ |result|
				this.prRecordRender(candidate, result);
				onSuccess.value(candidate)
			},
			{ |error|
				candidate[\status] = if(candidate[\render].notNil) { \rendered } { \proposed };
				if(error.kind == \render) { candidate[\error] = error };
				this.prWriteCandidate(candidate);
				onFailure.value(error)
			})
	}

	prCandidateFor { |index, failure|
		var candidate = if(index.isKindOf(Integer)) { candidates[index] };
		var problem = case
		{ candidate.isNil } { "there is no candidate " ++ index.asString ++ " in this session" }
		{ candidate[\proposal].isNil or: { candidate[\project].isNil } } {
			"candidate " ++ (index + 1) ++ " failed and has no code to use"
		};
		if(problem.notNil) {
			AppClock.sched(0, { failure.value(MBError(\validation, problem)); nil });
			^nil
		};
		^candidate
	}

	prNext { |index|
		var seed, requestContext;
		if(state != \running) { ^this };
		if(index >= maxCandidates) {
			state = \done;
			^this.prDone
		};
		seed = seeds[index];
		requestContext = context.copy;
		requestContext[\seed] = seed;
		requestContext[\variation] = (index: index + 1, count: maxCandidates);
		current = agent.propose(prompt, requestContext,
			{ |proposal|
				current = nil;
				if(state == \running) { this.prAccept(index, seed, proposal) };
			},
			{ |error|
				current = nil;
				if(state == \running) { this.prProposeFailed(index, seed, error) };
			});
	}

	prNewCandidate { |index, seed|
		var candidate = (
			index: index,
			number: index + 1,
			seed: seed,
			prompt: prompt,
			dir: dir +/+ ("candidate-" ++ (index + 1).asStringToBase(10, 2)),
			status: \proposing,
			code: Dictionary.new,
			render: nil,
			checks: nil,
			error: nil
		);
		File.mkdir(candidate[\dir]);
		candidates.add(candidate);
		^candidate
	}

	prProposeFailed { |index, seed, error|
		var candidate;
		if([\parse, \validation].includes(error.kind)) {
			candidate = this.prNewCandidate(index, seed);
			candidate[\status] = \failed;
			candidate[\error] = error;
			this.prWriteCandidate(candidate);
			this.prContinue(candidate, index);
		} {
			state = if(error.kind == \cancelled) { \stopped } { \failed };
			this.prWriteSession;
			doneCalled = true;
			AppClock.sched(0, { onFailure.value(error); nil });
		};
	}

	prAccept { |index, seed, proposal|
		var candidate = this.prNewCandidate(index, seed), outcome;
		outcome = MBWorkflowTry.mbError({ this.prMaterialize(candidate, proposal) }, \io);
		if(outcome.isKindOf(MBError)) {
			candidate[\status] = \failed;
			candidate[\error] = outcome;
			this.prWriteCandidate(candidate);
			^this.prContinue(candidate, index)
		};
		candidate[\status] = \proposed;
		this.prWriteCandidate(candidate);
		if(approveRenders.not) { ^this.prContinue(candidate, index) };
		candidate[\status] = \rendering;
		current = MBRenderer.render(candidate[\project], candidate[\entry], candidate[\settings], true, nil,
			{ |result|
				current = nil;
				if(state == \running) {
					this.prRecordRender(candidate, result);
					this.prContinue(candidate, index);
				};
			},
			{ |error|
				current = nil;
				if(state == \running) {
					candidate[\status] = \failed;
					candidate[\error] = error;
					this.prWriteCandidate(candidate);
					this.prContinue(candidate, index);
				};
			});
	}

	prRecordRender { |candidate, result|
		candidate[\render] = result;
		candidate[\checks] = result[\checks];
		candidate[\status] = \rendered;
		candidate[\error] = nil;
		this.prWriteCandidate(candidate);
	}

	// Notify, then continue only if the user did not stop the session in the callback.
	prContinue { |candidate, index|
		this.prWriteSession;
		AppClock.sched(0, {
			onCandidate.value(candidate);
			this.prNext(index + 1);
			nil
		});
	}

	prMaterialize { |candidate, proposal|
		var root = candidate[\dir] +/+ "project", files = project.files, total = 0, candidateProject, entry, settings;
		files.do { |path| total = total + File.fileSize(project.resolve(path)) };
		if(total > maxCopyBytes) {
			MBError(\validation, "the project is too large to copy into a sampling session").throw
		};
		files.do { |path|
			var target = root +/+ path;
			File.mkdir(target.dirname);
			File.copy(project.resolve(path), target);
			if(File.exists(target).not) {
				MBError(\io, "could not copy " ++ path.quote ++ " into the session workspace").throw
			};
		};
		File.mkdir(root);
		candidateProject = MBProject.open(root);
		if(proposal[\edits].notEmpty) { candidateProject.prApply(proposal) };
		entry = context[\entry] ? proposal[\entry];
		if(entry.isNil) {
			entry = proposal[\edits].detect { |edit| edit.path.toLower.endsWith(".scd") };
			entry = entry !? { entry.path };
		};
		if(entry.isNil or: { candidateProject.exists(entry).not }) {
			MBError(\validation, "the candidate has no composition to render; select an entry composition").throw
		};
		settings = (duration: 30.0, sampleRate: 48000, numChannels: 2);
		proposal[\render] !? { |render| settings.putAll(render) };
		renderSettings !? { settings.putAll(renderSettings) };
		settings[\seed] = candidate[\seed];
		settings[\name] = "candidate-" ++ candidate[\number];
		settings[\metadata] = (summary: proposal[\summary], prompt: prompt, provider: proposal[\provider],
			model: proposal[\model], candidate: candidate[\number].asString, sessionId: id);
		proposal[\edits].do { |edit| candidate[\code][edit.path] = edit.after };
		candidate.putAll((
			proposal: proposal,
			project: candidateProject,
			projectDir: root,
			entry: entry,
			settings: settings,
			plan: proposal[\plan],
			summary: proposal[\summary],
			diff: proposal[\edits].collect(_.diffString).join("\n")
		));
	}

	prCandidateRecord { |candidate|
		var settings = candidate[\settings];
		^(
			number: candidate[\number],
			seed: candidate[\seed],
			status: candidate[\status].asString,
			prompt: candidate[\prompt],
			plan: candidate[\plan],
			summary: candidate[\summary],
			entry: candidate[\entry],
			settings: settings !? { (duration: settings[\duration], sampleRate: settings[\sampleRate],
				numChannels: settings[\numChannels], seed: settings[\seed]) },
			edits: candidate[\proposal] !? { |proposal| proposal[\edits].collect(_.asMetadata) },
			render: candidate[\render] !? { |render| render[\path].basename },
			checks: candidate[\checks],
			error: candidate[\error] !? { |error| (kind: error.kind, detail: error.detail) }
		)
	}

	prWriteCandidate { |candidate|
		MBWorkflowTry.value({
			MBProject.writeFile(candidate[\dir] +/+ "candidate.json",
				MBWorkflowJSON.stringify(this.prCandidateRecord(candidate)))
		});
	}

	prWriteSession {
		MBWorkflowTry.value({
			MBProject.writeFile(dir +/+ "session.json", MBWorkflowJSON.stringify((
				format: "maxxedbeats.session/1",
				id: id,
				prompt: prompt,
				state: state.asString,
				maxCandidates: maxCandidates,
				seeds: seeds.keep(maxCandidates),
				approveRenders: approveRenders,
				candidates: candidates.collect { |candidate| this.prCandidateRecord(candidate) }.asArray
			)))
		});
	}

	prDone {
		if(doneCalled.not) {
			doneCalled = true;
			this.prWriteSession;
			AppClock.sched(0, { onDone.value(candidates.copy.asArray, state == \stopped); nil });
		};
	}
}
