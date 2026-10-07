// State and actions of the MaxxedBeats agent window, independent of Qt.
// All provider, key, project, render, and variation work goes through the
// `services` port (an Event of functions, documented in docs/design/gui.md).
// Writing files, removing keys, rendering, undoing, and clearing history
// first set `pendingConfirm`; only `confirm` runs them. Generated code is
// never evaluated here. Dependants receive `update(controller, \state)`.

MBGuiController {
	classvar <maxCandidatesLimit = 4;

	var <services, <providers, <providerId, <modelId, <models, <modelsStale = false;
	var <modelsLastRefreshed, <modelMessage, <modelRefreshing = false;
	var <keyStatus, <project, <entryPath, <conversation;
	var <status = "", <progress, <error, <busy, busyHandle, token = 0;
	var <proposal, <proposalState, <lastUsage, <sessionTotals, <history;
	var <pendingConfirm, <renderResult, <renderSettings, <variation, varToken = 0;
	var <playing, playHandle, <closed = false;

	*new { |services| ^super.new.init(services) }

	init { |argServices|
		services = argServices ? ();
		providers = [];
		models = [];
		keyStatus = IdentityDictionary.new;
		conversation = List.new;
		history = [];
		renderSettings = (duration: 8, sampleRate: 48000, numChannels: 2);
		variation = (running: false, candidates: List.new, max: maxCandidatesLimit);
		this.loadProviders;
	}

	loadProviders {
		^this.attempt({ providers = (this.call(\providers) ? []).asArray }, "Could not list providers.")
	}

	// ---- service port -------------------------------------------------------

	call { |name ...args|
		var function = services[name];
		if(function.isNil) {
			MBError(\config, "The MaxxedBeats service '" ++ name ++ "' is not available.").throw
		};
		^function.valueArray(args)
	}

	// Runs `function`; a synchronous exception becomes a visible error.
	// Answers whether the function completed without throwing.
	// MBWorkflowTry instead of `try`: on sclang 3.14.1 a plain `try` that
	// catches an error raised during argument evaluation corrupts the caller.
	attempt { |function, failureStatus|
		var outcome = MBWorkflowTry.value({ function.value; \mbGuiOk });
		if(outcome.isKindOf(Exception)) { this.showError(outcome, failureStatus); ^false };
		^true
	}

	notify { if(closed.not) { this.changed(\state) } }

	showError { |e, statusText, secrets|
		error = MBGuiFormat.asError(e, secrets);
		status = statusText ?? { "Failed: " ++ error.kind };
		this.notify;
	}

	dismissError { error = nil; this.notify }

	setStatus { |text| status = text; this.notify }

	start {
		if(providers.isEmpty) { this.loadProviders };
		providers.do { |info| if(this.requiresKey(info[\id])) { this.checkKey(info[\id]) } };
		if(providers.notEmpty and: { providerId.isNil }) { this.selectProvider(providers[0][\id]) };
		this.refreshUsage;
		if(error.isNil) { status = "Ready. Open a project folder, then choose your DJ." };
		this.notify;
	}

	close {
		if(closed) { ^this };
		if(busy.notNil and: { this.cancellable }) { this.cancel };
		if(variation[\running]) { this.stopVariations };
		if(playHandle.notNil) { this.stopPlayback };
		closed = true;
	}

	// ---- provider and model ("Choose your DJ") --------------------------

	providerInfo { |id| ^providers.detect { |p| p[\id] == id.asSymbol } }

	requiresKey { |id| ^(this.providerInfo(id) ?? { () })[\requiresKey] != false }

	selectProvider { |id|
		var info = this.providerInfo(id);
		if(info.isNil) { ^this.showError(MBError(\validation, "Unknown provider: " ++ id)) };
		if(this.isWorking and: { info[\id] != providerId }) {
			^this.showError(MBError(\validation,
				"Finish or cancel the current request before choosing another DJ."))
		};
		providerId = info[\id];
		this.attempt({
			this.loadModels;
			modelId = this.call(\selectedModel, providerId) !? { |m| m.asString };
		}, "Could not read the model list.");
		this.updateModelMessage;
		if(this.requiresKey(providerId)) { this.checkKey(providerId) };
		status = "DJ: " ++ this.djText;
		this.notify;
	}

	loadModels {
		models = (this.call(\models, providerId) ? []).asArray;
		modelsLastRefreshed = this.call(\lastRefreshed, providerId);
		modelsStale = this.call(\isStale, providerId) == true;
	}

	modelInfo { |id|
		if(id.isNil) { ^nil };
		^models.detect { |m| m[\id].asString == id.asString }
	}

	modelUsable { ^(this.modelInfo(modelId) ?? { () })[\usable] == true }

	djText {
		^"provider " ++ (providerId ? "none") ++ " · model " ++ (modelId ? "none selected")
	}

	updateModelMessage {
		var info = this.modelInfo(modelId);
		var parts = List.new;
		case
		{ providerId.isNil } { parts.add("No provider available.") }
		{ models.isEmpty and: { modelId.isNil } } {
			parts.add("No model list for " ++ providerId ++ " yet: press Refresh models.")
		}
		{ modelId.isNil } { parts.add("Choose a model for " ++ providerId ++ ".") }
		{ info.isNil } {
			parts.add("Selected model " ++ modelId ++ " is not in " ++ providerId
				++ "'s model list (UNAVAILABLE). Choose another model; MaxxedBeats never switches models automatically.")
		}
		{ info[\usable] != true } {
			parts.add("Selected model " ++ modelId ++ " is unavailable"
				++ (info[\note] !? { |n| ": " ++ n } ? "")
				++ ". Choose another model; MaxxedBeats never switches models automatically.")
		};
		if(modelsStale and: { models.notEmpty }) {
			parts.add("Model list may be stale (last refreshed "
				++ MBGuiFormat.timeText(modelsLastRefreshed) ++ ").")
		} {
			if(modelsLastRefreshed.notNil) { parts.add("Model list refreshed " ++ MBGuiFormat.timeText(modelsLastRefreshed) ++ ".") };
		};
		modelMessage = parts.join(" ");
	}

	refreshModels {
		var id = providerId, ok;
		if(id.isNil) { ^this.showError(MBError(\validation, "Choose a provider first.")) };
		modelRefreshing = true;
		status = "Refreshing the " ++ id ++ " model list...";
		this.notify;
		ok = this.attempt({
			this.call(\refreshModels, id, { |...ignored|
				if(closed.not) {
					modelRefreshing = false;
					if(id == providerId) { this.attempt({ this.loadModels }); this.updateModelMessage };
					status = "Model list for " ++ id ++ " refreshed.";
					this.notify;
				}
			}, { |e|
				if(closed.not) {
					modelRefreshing = false;
					if(id == providerId) {
						this.attempt({ this.loadModels });
						modelsStale = true;
						this.updateModelMessage;
					};
					this.showError(e, "Model refresh failed for " ++ id
						++ "; any cached list shown may be stale.");
				}
			})
		}, "Model refresh failed.");
		if(ok.not) { modelRefreshing = false; this.notify };
	}

	selectModel { |id|
		var info = this.modelInfo(id);
		if(this.isWorking) {
			^this.showError(MBError(\validation, "Finish or cancel the current request before changing the model."))
		};
		if(info.isNil) {
			^this.showError(MBError(\unavailableModel, "Model " ++ id ++ " is not in the "
				++ providerId ++ " model list."))
		};
		if(info[\usable] != true) {
			^this.showError(MBError(\unavailableModel, "Model " ++ id ++ " is unavailable for "
				++ providerId ++ (info[\note] !? { |n| ": " ++ n } ? "") ++ "."))
		};
		this.attempt({
			var problem = this.call(\selectModel, providerId, info[\id].asString);
			if(problem.isKindOf(Exception)) { problem.throw };
			modelId = info[\id].asString;
			error = nil;
		}, "Could not save the model selection.");
		this.updateModelMessage;
		status = "DJ: " ++ this.djText;
		this.notify;
	}

	// ---- API keys ---------------------------------------------------------

	checkKey { |id|
		id = id.asSymbol;
		if(keyStatus[id].isNil) { keyStatus[id] = \checking };
		this.attempt({
			this.call(\hasKey, id, { |has|
				if(closed.not) { keyStatus[id] = if(has == true) { \stored } { \missing }; this.notify }
			})
		}, "Could not check the credential store.");
	}

	storeKey { |id, key|
		id = id.asSymbol;
		key = (key ? "").asString;
		if(key.size == 0) { ^this.showError(MBError(\validation, "Enter or paste an API key first.")) };
		if(key.any { |char| char.isSpace or: { char == $* } }) {
			^this.showError(MBError(\validation,
				"The key contains spaces or invalid characters. Clear the field and paste the key exactly as issued."))
		};
		keyStatus[id] = \saving;
		status = "Saving the " ++ id ++ " key to the OS credential store...";
		this.notify;
		this.attempt({
			this.call(\storeKey, id, key, { |...ignored|
				if(closed.not) {
					keyStatus[id] = \stored;
					status = "Saved the " ++ id ++ " key in the OS credential store.";
					this.notify;
				}
			}, { |e|
				if(closed.not) {
					keyStatus[id] = nil;
					this.checkKey(id);
					this.showError(e, "Saving the " ++ id ++ " key failed.", [key]);
				}
			})
		}, "Saving the key failed.");
	}

	removeKey { |id|
		id = id.asSymbol;
		this.requestConfirm(\removeKey,
			"Remove the stored " ++ id ++ " API key from the OS credential store? "
			++ "Requests to " ++ id ++ " will fail until you add a key again.", {
				keyStatus[id] = \removing;
				this.attempt({
					this.call(\removeKey, id, { |...ignored|
						if(closed.not) {
							keyStatus[id] = \missing;
							status = "Removed the " ++ id ++ " key.";
							this.notify;
						}
					}, { |e|
						if(closed.not) { keyStatus[id] = nil; this.checkKey(id); this.showError(e, "Removing the key failed.") }
					})
				}, "Removing the key failed.");
			});
	}

	validateKey { |id|
		id = id.asSymbol;
		keyStatus[id] = \validating;
		status = "Validating the " ++ id ++ " key with the provider...";
		this.notify;
		this.attempt({
			this.call(\validateKey, id, { |...ignored|
				if(closed.not) {
					keyStatus[id] = \valid;
					status = "The " ++ id ++ " key was accepted by the provider.";
					this.notify;
				}
			}, { |e|
				if(closed.not) {
					var mbError = MBGuiFormat.asError(e);
					keyStatus[id] = if(mbError.kind == \auth) { \invalid } { \stored };
					if(mbError.kind != \auth) { this.checkKey(id) };
					this.showError(mbError, "Key validation failed for " ++ id ++ ".");
				}
			})
		}, "Key validation failed.");
	}

	keyStatusText { |id|
		^switch(keyStatus[id.asSymbol],
			\stored, { "key stored" },
			\missing, { "no key" },
			\valid, { "key stored and valid" },
			\invalid, { "key stored but invalid (rejected by provider)" },
			\saving, { "saving..." },
			\removing, { "removing..." },
			\validating, { "validating..." },
			\checking, { "checking..." },
			{ "unknown" }
		)
	}

	// ---- project ----------------------------------------------------------

	openProject { |dir|
		dir = (dir ? "").asString;
		if(dir.size == 0) { ^this.showError(MBError(\validation, "Choose a project folder first.")) };
		if(this.isWorking) {
			^this.showError(MBError(\validation, "Finish or cancel the current work before switching projects."))
		};
		status = "Opening " ++ dir ++ "...";
		this.notify;
		this.attempt({
			this.call(\openProject, dir, { |info|
				if(closed.not) {
					project = info;
					entryPath = this.scdFiles.detect { |f| f.basename == "main.scd" } ?? { this.scdFiles.first };
					proposal = nil;
					proposalState = nil;
					renderResult = nil;
					progress = nil;
					error = nil;
					variation = (running: false, candidates: List.new, max: maxCandidatesLimit);
					conversation.add((role: \system, text: "Opened project " ++ info[\root]));
					status = "Project open: " ++ info[\root];
					this.notify;
				}
			}, { |e| if(closed.not) { this.showError(e, "Could not open the project.") } })
		}, "Could not open the project.");
	}

	projectFiles { ^if(project.isNil) { [] } { (project[\files] ? []).asArray } }

	scdFiles { ^this.projectFiles.select { |f| f.asString.toLower.endsWith(".scd") } }

	setEntry { |path| entryPath = path; this.notify }

	refreshProjectFiles {
		if(project.notNil and: { services[\projectFiles].notNil }) {
			this.attempt({ project[\files] = this.call(\projectFiles, project[\project]) });
		};
	}

	// ---- conversation and proposals ---------------------------------------

	isWorking { ^busy.notNil or: { variation[\running] == true } }

	cancellable { ^#[\propose, \render, \renderCandidate].includes(busy) }

	requestBlocker { |prompt|
		^case
		{ busy.notNil } { MBError(\validation, "Wait for the current " ++ busy ++ " to finish, or press Cancel.") }
		{ variation[\running] == true } { MBError(\validation, "Stop the variation session first.") }
		{ project.isNil } { MBError(\validation, "Open a project folder first.") }
		{ providerId.isNil } { MBError(\validation, "Choose your DJ (provider) first.") }
		{ this.requiresKey(providerId) and: { keyStatus[providerId] == \missing } } {
			MBError(\auth, "No API key is stored for " ++ providerId ++ ". Add one under Keys & Privacy.")
		}
		{ modelId.isNil } { MBError(\unavailableModel, "Choose a model for " ++ providerId ++ " first.") }
		{ this.modelUsable.not } { MBError(\unavailableModel, modelMessage) }
		{ prompt.isNil or: { prompt.asString.reject(_.isSpace).isEmpty } } {
			MBError(\validation, "Type a prompt first.")
		}
		{ nil }
	}

	conversationMessages {
		^conversation.select { |m| #[\user, \assistant].includes(m[\role]) }
			.collect { |m| (role: m[\role], content: m[\text]) }.asArray
	}

	send { |prompt, contextFiles|
		var blocker = this.requestBlocker(prompt), myToken, context, ok;
		if(blocker.isNil and: { proposalState == \pending }) {
			blocker = MBError(\validation, "Approve or reject the proposed changes first.")
		};
		if(blocker.notNil) { ^this.showError(blocker, "Not sent: " ++ blocker.detail) };
		prompt = prompt.asString;
		context = (files: (contextFiles ? []).asArray, entry: entryPath, history: this.conversationMessages);
		conversation.add((role: \user, text: prompt));
		myToken = this.beginBusy(\propose, "Asking " ++ this.djText ++ "...");
		ok = this.attempt({
			busyHandle = this.call(\propose, project[\project], providerId, modelId, prompt, context,
				this.guard(myToken, { |result| this.proposalArrived(result) }),
				this.guard(myToken, { |e|
					this.endBusy;
					conversation.add((role: \error, text: MBGuiFormat.errorText(e)));
					this.refreshUsage;
					this.showError(e, "Request failed; nothing was changed.");
				}))
		}, "Request failed; nothing was changed.");
		if(ok.not and: { token == myToken }) { this.endBusy; this.notify };
	}

	proposalArrived { |result|
		var edits = result[\edits] ? [];
		this.endBusy;
		proposal = result;
		proposalState = if(edits.isEmpty) { \noEdits } { \pending };
		this.adoptProposalSettings(result);
		lastUsage = result[\usage];
		conversation.add((role: \assistant, provider: providerId, model: modelId,
			text: (result[\summary] ? "(no summary)").asString));
		this.refreshUsage;
		error = nil;
		status = if(proposalState == \pending) {
			"Proposal ready (" ++ edits.size ++ " file change(s)): review the diff, then Approve or Reject."
		} { "The DJ replied without file changes." };
		this.notify;
	}

	// The proposal may suggest an entry file and render settings; adopt the
	// ones the window offers, so the render panel shows what will be used.
	adoptProposalSettings { |result|
		var suggested = result[\render], settings = renderSettings.copy;
		var entry = result[\entry];
		if(suggested.notNil) {
			suggested[\duration] !? { |d| if(d.isNumber and: { d > 0 } and: { d <= 600 }) { settings[\duration] = d } };
			suggested[\sampleRate] !? { |r| if(#[44100, 48000, 96000].includes(r)) { settings[\sampleRate] = r } };
			suggested[\numChannels] !? { |c| if(#[1, 2].includes(c)) { settings[\numChannels] = c } };
			renderSettings = settings;
		};
		if(entry.notNil and: { entry.asString.toLower.endsWith(".scd") }) { entryPath = entry.asString };
	}

	approveProposal {
		var edits;
		if(proposalState != \pending) { ^this.showError(MBError(\validation, "There are no proposed changes to approve.")) };
		if(busy.notNil) { ^this.showError(MBError(\validation, "Wait for the current " ++ busy ++ " to finish.")) };
		edits = proposal[\edits];
		this.requestConfirm(\apply, "Write " ++ edits.size ++ " file change(s) to " ++ project[\root]
			++ "? A backup is saved first; Undo restores it.", { this.applyProposal });
	}

	applyProposal {
		var myToken = this.beginBusy(\apply, "Applying the approved changes...");
		var ok = this.attempt({
			busyHandle = this.call(\apply, project[\project], proposal, true,
				this.guard(myToken, { |...ignored|
					this.endBusy;
					proposalState = \applied;
					this.refreshProjectFiles;
					conversation.add((role: \system, text: "Applied " ++ proposal[\edits].size ++ " change(s) after approval."));
					error = nil;
					status = "Applied " ++ proposal[\edits].size ++ " change(s). A backup was saved; Undo restores it.";
					this.notify;
				}),
				this.guard(myToken, { |e|
					this.endBusy;
					this.showError(e, "Applying the changes failed; the proposal is still pending.");
				}))
		}, "Applying the changes failed.");
		if(ok.not and: { token == myToken }) { this.endBusy; this.notify };
	}

	rejectProposal {
		if(proposalState != \pending) { ^this.showError(MBError(\validation, "There are no proposed changes to reject.")) };
		proposalState = \rejected;
		conversation.add((role: \system, text: "Rejected the proposed changes; project files unchanged."));
		status = "Rejected the proposal; nothing was written.";
		this.notify;
	}

	undo {
		if(project.isNil) { ^this.showError(MBError(\validation, "Open a project folder first.")) };
		if(this.isWorking) { ^this.showError(MBError(\validation, "Finish or cancel the current work first.")) };
		this.requestConfirm(\undo, "Undo the last applied change? Project files are restored from the most recent backup.", {
			var myToken = this.beginBusy(\undo, "Restoring the previous version...");
			var ok = this.attempt({
				busyHandle = this.call(\undo, project[\project],
					this.guard(myToken, { |...ignored|
						this.endBusy;
						this.refreshProjectFiles;
						conversation.add((role: \system, text: "Undo restored the previous version."));
						error = nil;
						status = "Restored the previous version from the backup.";
						this.notify;
					}),
					this.guard(myToken, { |e| this.endBusy; this.showError(e, "Undo failed; files were not restored.") }))
			}, "Undo failed.");
			if(ok.not and: { token == myToken }) { this.endBusy; this.notify };
		});
	}

	// ---- render and playback ------------------------------------------------

	setRenderSettings { |settings| renderSettings = settings; this.notify }

	renderSettingsError { |settings|
		var duration = settings[\duration];
		^case
		{ duration.isNumber.not or: { duration <= 0 } or: { duration > 600 } } {
			MBError(\validation, "Render duration must be between 0 and 600 seconds.")
		}
		{ #[44100, 48000, 96000].includes(settings[\sampleRate]).not } {
			MBError(\validation, "Sample rate must be 44100, 48000, or 96000 Hz.")
		}
		{ #[1, 2].includes(settings[\numChannels]).not } { MBError(\validation, "Channels must be 1 or 2.") }
		{ nil }
	}

	requestRender { |settings, entry|
		var problem;
		settings = settings ? renderSettings;
		entry = entry ? entryPath;
		problem = case
		{ busy.notNil } { MBError(\validation, "Wait for the current " ++ busy ++ " to finish, or press Cancel.") }
		{ variation[\running] == true } { MBError(\validation, "Stop the variation session first.") }
		{ project.isNil } { MBError(\validation, "Open a project folder first.") }
		{ entry.isNil } { MBError(\validation, "The project has no .scd file to render.") }
		{ this.renderSettingsError(settings) };
		if(problem.notNil) { ^this.showError(problem, "Not rendered: " ++ problem.detail) };
		renderSettings = settings;
		entryPath = entry;
		this.requestConfirm(\render, "Render " ++ entry ++ " to a new WAV file ("
			++ settings[\duration] ++ " s, " ++ settings[\sampleRate] ++ " Hz, "
			++ settings[\numChannels] ++ " ch)? This evaluates the project's composition code in a "
			++ "separate headless sclang process (never in this interpreter) and renders offline with scsynth."
			++ (if(proposalState == \pending) { " The pending proposal is NOT applied; the files on disk are rendered." } { "" }),
			{ this.startRender });
	}

	startRender {
		var myToken = this.beginBusy(\render, "Rendering " ++ entryPath ++ "..."), ok;
		progress = 0;
		renderResult = nil;
		ok = this.attempt({
			busyHandle = this.call(\render, project[\project], entryPath, this.renderRequestSettings, true,
				this.guard(myToken, { |p| this.renderProgress(p) }),
				this.guard(myToken, { |result|
					var warnings = MBGuiFormat.checkWarnings(result[\checks]);
					this.endBusy;
					progress = 1;
					renderResult = result;
					error = nil;
					status = "Render finished: " ++ result[\path]
						++ (if(warnings.isEmpty) { "" } { " (with warnings: " ++ warnings.join("; ") ++ ")" });
					this.notify;
				}),
				this.guard(myToken, { |e|
					this.endBusy;
					progress = nil;
					this.showError(e, "Render failed; no audio file was produced.");
				}))
		}, "Render failed; no audio file was produced.");
		if(ok.not and: { token == myToken }) { this.endBusy; progress = nil; this.notify };
	}

	renderRequestSettings {
		var settings = renderSettings.copy;
		if(proposal.notNil and: { proposalState == \applied }) {
			proposal[\seed] !? { |seed| settings[\seed] = seed };
			settings[\metadata] = (summary: proposal[\summary], prompt: proposal[\prompt],
				provider: proposal[\provider] !? (_.asString), model: proposal[\model], plan: proposal[\plan]);
		};
		^settings
	}

	renderProgress { |p|
		var fraction = if(p.isNumber) { p } { p !? { p[\fraction] } };
		var message = if(p.isNumber.not and: { p.notNil }) { p[\message] };
		if(fraction.isNumber) { progress = fraction.clip(0, 1) };
		status = (if(busy == \renderCandidate) { "Rendering candidate" } { "Rendering " ++ entryPath }) ++ "..."
			++ (if(progress.notNil) { " " ++ (progress * 100).round.asInteger ++ "%" } { "" })
			++ (message !? { |m| " " ++ m } ? "");
		this.notify;
	}

	play { |path|
		var target = path, failed = false;
		if(target.isNil) { ^this.showError(MBError(\validation, "Nothing has been rendered yet.")) };
		if(playHandle.notNil) { this.stopPlayback };
		failed = this.attempt({
			playHandle = this.call(\play, target, {
				if(closed.not) { playing = target; status = "Playing " ++ target; this.notify }
			}, { |...ignored|
				if(closed.not and: { playing == target }) { playing = nil; playHandle = nil; this.notify }
			}, { |e|
				failed = true;
				if(closed.not) { playing = nil; playHandle = nil; this.showError(e, "Playback failed.") }
			})
		}, "Playback failed.").not or: { failed };
		if(failed) { playHandle = nil; playing = nil } { if(playing.isNil) { status = "Starting playback of " ++ target ++ "..." } };
		this.notify;
	}

	isPlaying { ^playHandle.notNil or: { playing.notNil } }

	stopPlayback {
		var handle = playHandle;
		playHandle = nil;
		playing = nil;
		if(handle.notNil) { this.attempt({ this.call(\stopPlayback, handle) }) };
		this.notify;
	}

	reveal { |path|
		if(path.isNil) { ^this.showError(MBError(\validation, "Nothing has been rendered yet.")) };
		this.attempt({ this.call(\reveal, path) }, "Could not open the file browser.");
	}

	// ---- variations --------------------------------------------------------

	// Rendering candidates evaluates generated code in a separate process, so
	// `renderCandidates: true` first asks for confirmation; only then does the
	// session receive approveRenders: true.
	startVariations { |prompt, maxCandidates, renderCandidates = false, contextFiles|
		var blocker = this.requestBlocker(prompt), max;
		if(blocker.notNil) { ^this.showError(blocker, "Variation session not started: " ++ blocker.detail) };
		max = (maxCandidates ? maxCandidatesLimit).asInteger.clip(1, maxCandidatesLimit);
		if(renderCandidates != true) { ^this.runVariations(prompt, max, false, contextFiles) };
		this.requestConfirm(\variations, "Generate up to " ++ max ++ " candidate(s) with " ++ this.djText
			++ " (one provider request each; may incur cost) and render each one ("
			++ renderSettings[\duration] ++ " s) by evaluating its generated code in a separate headless "
			++ "sclang/scsynth process? Your project is not changed.", {
				this.runVariations(prompt, max, true, contextFiles)
			});
	}

	runVariations { |prompt, max, approveRenders, contextFiles|
		var myToken, ok, context;
		varToken = varToken + 1;
		myToken = varToken;
		context = (files: (contextFiles ? []).asArray, entry: entryPath);
		variation = (running: true, candidates: List.new, max: max, prompt: prompt.asString,
			renders: approveRenders, status: "Generating candidate 1 of " ++ max ++ "...");
		error = nil;
		status = "Variation session started with " ++ this.djText ++ " (up to " ++ max ++ " candidates"
			++ (if(approveRenders) { ", rendering each" } { ", not rendered" }) ++ ").";
		this.notify;
		ok = this.attempt({
			variation[\session] = this.call(\startVariations, project[\project], providerId, modelId,
				prompt.asString, max, approveRenders, renderSettings.copy, context,
				this.varGuard(myToken, { |candidate| this.candidateArrived(candidate) }),
				this.varGuard(myToken, { |...ignored|
					variation[\running] = false;
					variation[\status] = "Finished: " ++ variation[\candidates].size ++ " of "
						++ variation[\max] ++ " candidate(s).";
					status = "Variation session finished; the original project is unchanged.";
					this.refreshUsage;
					this.notify;
				}),
				this.varGuard(myToken, { |e|
					variation[\running] = false;
					variation[\status] = "Failed after " ++ variation[\candidates].size ++ " of "
						++ variation[\max] ++ " candidate(s); kept candidates remain available.";
					this.refreshUsage;
					this.showError(e, "Variation session failed.");
				}))
		}, "Variation session failed to start.");
		if(ok.not and: { varToken == myToken }) {
			variation[\running] = false;
			varToken = varToken + 1;
			this.notify;
		};
	}

	renderCandidate { |index|
		var candidate = this.candidateAt(index);
		if(candidate.isNil) { ^this };
		if(this.isWorking) { ^this.showError(MBError(\validation, "Stop the variation session and wait for running work first.")) };
		this.requestConfirm(\renderCandidate, "Render candidate #" ++ (index + 1) ++ "? Its generated code is "
			++ "evaluated in a separate headless sclang process and rendered offline with scsynth; the project is not changed.", {
				var myToken = this.beginBusy(\renderCandidate, "Rendering candidate #" ++ (index + 1) ++ "...");
				var ok = this.attempt({
					busyHandle = this.call(\renderCandidate, variation[\session], index,
						this.guard(myToken, { |p| this.renderProgress(p) }),
						this.guard(myToken, { |updated|
							this.endBusy;
							progress = 1;
							if(updated.notNil) { variation[\candidates][index] = updated };
							error = nil;
							status = "Rendered candidate #" ++ (index + 1) ++ ".";
							this.notify;
						}),
						this.guard(myToken, { |e|
							this.endBusy;
							progress = nil;
							this.showError(e, "Rendering candidate #" ++ (index + 1) ++ " failed.");
						}))
				}, "Rendering the candidate failed.");
				if(ok.not and: { token == myToken }) { this.endBusy; this.notify };
			});
	}

	candidateArrived { |candidate|
		var candidates = variation[\candidates];
		// A candidate beyond the limit means the service ignored the cap: stop it.
		if(candidates.size >= variation[\max]) { ^this.stopVariations("limit reached") };
		candidates.add(candidate);
		variation[\status] = "Running: " ++ candidates.size ++ " of " ++ variation[\max] ++ " candidate(s).";
		status = "Variation candidate " ++ candidates.size ++ " of " ++ variation[\max]
			++ (if(candidate[\status] == \failed) { " failed." } { " ready." });
		this.refreshUsage;
		this.notify;
	}

	stopVariations { |reason|
		var session = variation[\session];
		if(variation[\running] != true) { ^this };
		varToken = varToken + 1;
		variation[\running] = false;
		this.attempt({ this.call(\stopVariations, session) }, "Stopping the variation session failed.");
		variation[\status] = (if(reason.notNil) { "Done (" ++ reason ++ ")" } { "Stopped" })
			++ " at " ++ variation[\candidates].size ++ " of " ++ variation[\max] ++ " candidate(s).";
		status = "Variation session stopped; the original project is unchanged.";
		this.notify;
	}

	candidateAt { |index|
		var candidate = if(index.notNil) { variation[\candidates][index] };
		if(candidate.isNil) { this.showError(MBError(\validation, "Select a candidate first.")) };
		^candidate
	}

	auditionCandidate { |index|
		var candidate = this.candidateAt(index), path;
		if(candidate.isNil) { ^this };
		path = MBGuiFormat.candidateAudioPath(candidate);
		if(path.isNil) { ^this.showError(MBError(\validation, "This candidate has no rendered audio yet.")) };
		this.play(path);
	}

	applyCandidate { |index|
		var candidate = this.candidateAt(index);
		if(candidate.isNil) { ^this };
		if(this.isWorking) { ^this.showError(MBError(\validation, "Stop the variation session before applying a candidate.")) };
		this.requestConfirm(\applyCandidate, "Apply candidate #" ++ (index + 1) ++ " to "
			++ project[\root] ++ "? Its files replace the project's; a backup is saved first and Undo restores it.", {
				var myToken = this.beginBusy(\applyCandidate, "Applying candidate #" ++ (index + 1) ++ "...");
				var ok = this.attempt({
					busyHandle = this.call(\applyVariation, variation[\session], index, true,
						this.guard(myToken, { |...ignored|
							this.endBusy;
							this.refreshProjectFiles;
							conversation.add((role: \system, text: "Applied variation candidate #" ++ (index + 1) ++ " after confirmation."));
							error = nil;
							status = "Applied candidate #" ++ (index + 1) ++ ". A backup was saved; Undo restores it.";
							this.notify;
						}),
						this.guard(myToken, { |e| this.endBusy; this.showError(e, "Applying the candidate failed.") }))
				}, "Applying the candidate failed.");
				if(ok.not and: { token == myToken }) { this.endBusy; this.notify };
			});
	}

	// ---- usage ------------------------------------------------------------

	refreshUsage {
		this.attempt({
			sessionTotals = this.call(\sessionTotals);
			history = (this.call(\history) ? []).asArray;
		}, "Could not read usage.");
	}

	clearHistory {
		this.requestConfirm(\clearHistory, "Clear the local usage history? This only deletes the history stored on this computer.", {
			this.attempt({
				this.call(\clearHistory);
				this.refreshUsage;
				status = "Cleared the local usage history.";
			}, "Clearing the usage history failed.");
		});
	}

	// ---- confirmation, busy state, cancellation ---------------------------

	requestConfirm { |kind, message, action|
		pendingConfirm = (kind: kind, message: message, action: action);
		status = "Confirmation needed.";
		this.notify;
	}

	confirm {
		var pending = pendingConfirm;
		if(pending.isNil) { ^this };
		pendingConfirm = nil;
		pending[\action].value;
		this.notify;
	}

	cancelConfirm {
		if(pendingConfirm.isNil) { ^this };
		pendingConfirm = nil;
		status = "Cancelled; nothing was changed.";
		this.notify;
	}

	beginBusy { |kind, statusText|
		token = token + 1;
		busy = kind;
		busyHandle = nil;
		progress = nil;
		error = nil;
		status = statusText;
		this.notify;
		^token
	}

	endBusy { busy = nil; busyHandle = nil }

	guard { |myToken, function|
		^{ |...args| if(closed.not and: { token == myToken }) { function.valueArray(args) } }
	}

	varGuard { |myToken, function|
		^{ |...args| if(closed.not and: { varToken == myToken }) { function.valueArray(args) } }
	}

	cancel {
		var handle = busyHandle, kind = busy;
		if(kind.isNil) { ^this };
		if(this.cancellable.not) {
			^this.showError(MBError(\validation, "The current " ++ kind ++ " cannot be cancelled safely; wait for it to finish."))
		};
		token = token + 1;
		this.endBusy;
		progress = nil;
		this.attempt({ this.call(\cancel, handle) });
		if(kind == \propose) { conversation.add((role: \system, text: "Request cancelled.")) };
		status = "Cancelled the " ++ kind ++ "; nothing was changed.";
		this.notify;
	}
}
