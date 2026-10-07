// Qt window for the MaxxedBeats agent. Builds the views, forwards user
// actions to MBGuiController, and redraws everything from controller state
// on every change. `views` maps stable names to widgets so tests and the
// visual-test driver can exercise the real widgets' actions.

MBGuiWindow {
	var <controller, <window, <views, <masks, stack, keyProviderIds, modelItemIds;
	var refreshing = false, shown;

	*new { |controller, bounds| ^super.new.init(controller, bounds) }

	init { |argController, bounds|
		controller = argController;
		views = IdentityDictionary.new;
		masks = IdentityDictionary.new;
		shown = IdentityDictionary.new;
		modelItemIds = [];
		this.build(bounds ?? { Rect(80, 80, 1180, 800) });
		controller.addDependant(this);
		this.refresh;
	}

	front { window.front }

	close {
		this.cleanup;
		if(window.notNil and: { window.isClosed.not }) { window.close };
	}

	cleanup {
		controller.removeDependant(this);
		controller.close;
		if(MaxxedBeats.current === this) { MaxxedBeats.clearCurrent };
	}

	isClosed { ^window.isNil or: { window.isClosed } }

	update { |who, what| if(this.isClosed.not) { this.refresh } }

	// ---- construction ------------------------------------------------------

	label { |text, bold = false|
		var view = StaticText().string_(text);
		if(bold) { view.font = Font.sansSerif(12, true) };
		^view
	}

	button { |key, text, action|
		^this.keep(key, Button().states_([[text]]).action_({ action.value }))
	}

	readOnlyText { |key, height|
		var view = TextView().editable_(false).font_(Font.monospace(11));
		if(height.notNil) { view.minHeight = height };
		^this.keep(key, view)
	}

	keep { |key, view|
		views[key] = view;
		^view
	}

	build { |bounds|
		var tabNames = [[\tabCompose, "Compose"], [\tabVariations, "Variations"],
			[\tabKeys, "Keys && Privacy"], [\tabUsage, "Usage"]];
		window = Window("MaxxedBeats — AI music assistant", bounds);
		window.view.minSize = Size(980, 680);
		window.onClose = { this.cleanup };
		stack = StackLayout(this.buildComposePage, this.buildVariationsPage,
			this.buildKeysPage, this.buildUsagePage);
		window.layout = VLayout(
			this.buildProjectRow,
			this.buildDJRow,
			this.keep(\modelMessage, StaticText().string_("")),
			this.buildStatusRow,
			this.buildErrorRow,
			this.buildConfirmPanel,
			HLayout(*(tabNames.collect { |pair, i|
				this.button(pair[0], pair[1], { this.showTab(i) })
			} ++ [nil])),
			stack
		);
		this.showTab(0);
	}

	showTab { |index|
		stack.index = index;
		[\tabCompose, \tabVariations, \tabKeys, \tabUsage].do { |key, i|
			views[key].font = Font.sansSerif(12, i == index);
		};
	}

	buildProjectRow {
		views[\projectPath] = TextField().string_("")
			.toolTip_("Project folder containing your .scd composition files");
		views[\projectPath].action = { controller.openProject(views[\projectPath].string) };
		^HLayout(
			this.label("Project folder", true),
			[views[\projectPath], stretch: 1],
			this.button(\chooseProject, "Choose...", {
				FileDialog({ |paths|
					views[\projectPath].string = paths[0];
					controller.openProject(paths[0]);
				}, nil, 2, 0)
			}),
			this.button(\openProject, "Open", { controller.openProject(views[\projectPath].string) }),
			[this.keep(\projectLabel, StaticText().string_("No project open")), stretch: 1]
		)
	}

	buildDJRow {
		views[\djLabel] = this.label("Choose your DJ", true);
		views[\provider] = PopUpMenu().minWidth_(180);
		views[\provider].action = { |menu|
			var info = controller.providers[menu.value];
			if(info.notNil) { controller.selectProvider(info[\id]) };
			this.refresh;
		};
		views[\model] = PopUpMenu().minWidth_(320);
		views[\model].action = { |menu|
			var id = modelItemIds[menu.value];
			if(id.notNil) { controller.selectModel(id) };
			this.refresh;
		};
		^HLayout(
			views[\djLabel],
			views[\provider],
			views[\model],
			this.button(\refreshModels, "Refresh models", { controller.refreshModels }),
			[this.keep(\djIds, StaticText().string_("")), stretch: 1]
		)
	}

	buildStatusRow {
		views[\progress] = UserView().fixedSize_(Size(180, 16)).drawFunc_({ |view|
			var p = controller.progress;
			Pen.color = Color.gray(0.85);
			Pen.fillRect(view.bounds.moveTo(0, 0));
			if(p.notNil) {
				Pen.color = Color(0.2, 0.55, 0.3);
				Pen.fillRect(Rect(0, 0, view.bounds.width * p, view.bounds.height));
			};
		});
		^HLayout(
			[this.keep(\status, StaticText().string_("")), stretch: 1],
			views[\progress],
			this.button(\cancel, "Stop request", { controller.cancel })
		)
	}

	buildErrorRow {
		views[\error] = StaticText().stringColor_(Color(0.7, 0, 0)).string_("");
		views[\errorRow] = View().background_(Color(1, 0.92, 0.92)).layout_(HLayout(
			[views[\error], stretch: 1],
			this.button(\dismissError, "Dismiss", { controller.dismissError })
		).margins_(4));
		^views[\errorRow]
	}

	buildConfirmPanel {
		views[\confirmText] = StaticText().string_("");
		views[\confirmPanel] = View().background_(Color(1, 0.96, 0.8)).layout_(HLayout(
			[views[\confirmText], stretch: 1],
			this.button(\confirm, "Confirm", { controller.confirm }),
			this.button(\cancelConfirm, "Cancel", { controller.cancelConfirm })
		).margins_(6));
		^views[\confirmPanel]
	}

	buildComposePage {
		var left, right;
		views[\contextFiles] = ListView().selectionMode_(\multi).minHeight_(70)
			.toolTip_("Only the files you select here are sent to the provider as context.");
		views[\prompt] = TextView().minHeight_(60).maxHeight_(90);
		views[\entry] = PopUpMenu().minWidth_(140);
		views[\entry].action = { |menu| controller.setEntry(menu.item) };
		views[\duration] = NumberBox().value_(8).clipLo_(0).clipHi_(600).decimals_(1).fixedWidth_(60);
		views[\sampleRate] = PopUpMenu().items_(["44100", "48000", "96000"]).value_(1);
		views[\channels] = PopUpMenu().items_(["1", "2"]).value_(1);
		[\duration, \sampleRate, \channels].do { |key| views[key].action = { controller.setRenderSettings(this.renderSettingsFromViews) } };
		left = VLayout(
			this.label("Context files sent to the DJ (select; none = prompt only)"),
			views[\contextFiles],
			this.label("Conversation"),
			[this.readOnlyText(\conversation, 120), stretch: 2],
			this.label("Your prompt"),
			views[\prompt],
			HLayout(
				this.button(\send, "Send to DJ", { this.send }),
				[this.keep(\usageLast, StaticText().string_("")), stretch: 1]
			)
		);
		right = VLayout(
			this.label("Proposed musical plan", true),
			[this.readOnlyText(\plan, 70), stretch: 1],
			this.label("Proposed changes (review the diff before approving)", true),
			[this.readOnlyText(\diff, 120), stretch: 2],
			HLayout(
				this.button(\approve, "Approve and apply...", { controller.approveProposal }),
				this.button(\reject, "Reject", { controller.rejectProposal }),
				this.button(\undo, "Undo last apply...", { controller.undo }),
				nil
			),
			this.label("Render (offline, separate process)", true),
			HLayout(
				this.label("Entry"), views[\entry],
				this.label("Seconds"), views[\duration],
				this.label("Hz"), views[\sampleRate],
				this.label("Ch"), views[\channels],
				this.button(\render, "Render...", { this.render }),
				nil
			),
			this.readOnlyText(\renderResult, 56).maxHeight_(70),
			HLayout(
				this.button(\play, "Play preview", { controller.play(controller.renderResult !? { |r| r[\path] }) }),
				this.button(\stopPlay, "Stop", { controller.stopPlayback }),
				this.button(\reveal, "Reveal file", { controller.reveal(controller.renderResult !? { |r| r[\path] }) }),
				nil
			)
		);
		^View().layout_(HLayout([left, stretch: 1], [right, stretch: 1]).margins_(0))
	}

	buildVariationsPage {
		views[\varPrompt] = TextView().minHeight_(50).maxHeight_(80);
		views[\varMax] = NumberBox().value_(MBGuiController.maxCandidatesLimit).clipLo_(1)
			.clipHi_(MBGuiController.maxCandidatesLimit).decimals_(0).step_(1).fixedWidth_(40);
		views[\candidates] = ListView().action_({ this.refreshCandidateReview });
		views[\candidateReview] = TextView().editable_(false).minHeight_(100);
		^View().layout_(VLayout(
			this.label("Variation session: the DJ proposes up to the limit of candidates in a separate session folder. "
				++ "Review each candidate before rendering. Your project is unchanged until you apply one."),
			this.label("Variation prompt"),
			views[\varPrompt],
			HLayout(
				this.label("Max candidates (1-" ++ MBGuiController.maxCandidatesLimit ++ ")"),
				views[\varMax],
				this.button(\varStart, "Start session", {
					controller.setRenderSettings(this.renderSettingsFromViews);
					controller.startVariations(views[\varPrompt].string, views[\varMax].value.asInteger,
						false, this.selectedContextFiles)
				}),
				this.button(\varStop, "Stop", { controller.stopVariations }),
				[this.keep(\varStatus, StaticText().string_("")), stretch: 1]
			),
			[views[\candidates], stretch: 1],
			[views[\candidateReview], stretch: 1],
			HLayout(
				this.button(\audition, "Audition selected", { controller.auditionCandidate(views[\candidates].value) }),
				this.button(\stopAudition, "Stop", { controller.stopPlayback }),
				this.button(\renderCandidate, "Render selected...", {
					this.refreshCandidateReview;
					controller.renderCandidate(views[\candidates].value)
				}),
				this.button(\applyCandidate, "Apply selected...", { controller.applyCandidate(views[\candidates].value) }),
				nil
			)
		))
	}

	buildKeysPage {
		var rows;
		keyProviderIds = controller.providers.select { |p| p[\requiresKey] != false }.collect { |p| p[\id] };
		views[\privacyNotice] = StaticText().string_(MBGuiFormat.privacyNotice).align_(\topLeft);
		rows = keyProviderIds.collect { |id| this.buildKeyRow(id) };
		^View().layout_(VLayout(*([[views[\privacyNotice], stretch: 0]] ++ rows ++ [nil])))
	}

	buildKeyRow { |id|
		var mask = MBMaskedField.new;
		var info = controller.providerInfo(id);
		var key = { |name| (name ++ "_" ++ id).asSymbol };
		masks[id] = mask;
		views[key.("keyField")] = mask.field.minWidth_(160);
		views[key.("keyMask")] = mask.display.minWidth_(240);
		views[key.("keyStatus")] = StaticText().minWidth_(220);
		^HLayout(
			this.label(MBGuiFormat.providerLabel(info), true).minWidth_(150),
			views[key.("keyStatus")],
			mask.field,
			mask.display,
			this.button(key.("keySave"), "Save / replace", {
				controller.storeKey(id, mask.secret);
				mask.clear;
			}),
			this.button(key.("keyClear"), "Clear", { mask.clear }),
			this.button(key.("keyValidate"), "Validate", { controller.validateKey(id) }),
			this.button(key.("keyRemove"), "Remove...", { controller.removeKey(id) }),
			nil
		)
	}

	buildUsagePage {
		views[\history] = ListView();
		^View().layout_(VLayout(
			this.keep(\rateNote, StaticText().string_(MBGuiFormat.creditNote)),
			this.label("Last request", true),
			this.keep(\usageLastDetail, StaticText().string_("")),
			this.label("This session", true),
			this.keep(\usageSession, StaticText().string_("")),
			this.label("History (stored only on this computer)", true),
			[views[\history], stretch: 1],
			HLayout(this.button(\clearHistory, "Clear history...", { controller.clearHistory }), nil)
		))
	}

	// ---- user actions that read several widgets ------------------------------

	selectedContextFiles {
		var files = controller.projectFiles;
		^(views[\contextFiles].selection ? []).collect { |i| files[i] }.reject(_.isNil)
	}

	send {
		var prompt = views[\prompt].string;
		controller.send(prompt, this.selectedContextFiles);
		if(controller.busy == \propose) { views[\prompt].string = "" };
	}

	renderSettingsFromViews {
		^(
			duration: views[\duration].value,
			sampleRate: views[\sampleRate].item.asInteger,
			numChannels: views[\channels].item.asInteger
		)
	}

	render {
		var scd = controller.scdFiles;
		controller.requestRender(this.renderSettingsFromViews, if(scd.notEmpty) { scd[views[\entry].value ? 0] });
	}

	// ---- redraw from controller state ---------------------------------------

	refresh {
		var c = controller;
		var idle = c.busy.isNil;
		var working = c.isWorking;
		var project = c.project;
		var files = c.projectFiles;
		var scd = c.scdFiles;
		var variation = c.variation;
		var candidates = variation[\candidates];
		if(refreshing) { ^this };
		refreshing = true;

		views[\projectLabel].string = if(project.isNil) { "No project open" } {
			"Open: " ++ MBGuiFormat.baseName(project[\root]) ++ " (" ++ MBGuiFormat.fileCount(files.size) ++ ")"
		};
		views[\projectLabel].toolTip = if(project.isNil) { "" } { project[\root].asString };
		views[\openProject].enabled = working.not;
		views[\chooseProject].enabled = working.not;

		this.refreshDJ;

		views[\status].string = c.status ? "";
		views[\progress].refresh;
		views[\cancel].enabled = c.cancellable;
		this.setShown(\errorRow, c.error.notNil);
		views[\error].string = if(c.error.notNil) { MBGuiFormat.errorText(c.error) } { "" };
		this.setShown(\confirmPanel, c.pendingConfirm.notNil);
		views[\confirm].enabled = c.pendingConfirm.notNil and: { working.not };
		views[\confirmText].string = if(c.pendingConfirm.notNil) { c.pendingConfirm[\message] } { "" };

		this.setItems(\contextFiles, files);
		this.setItems(\entry, scd);
		if(c.entryPath.notNil and: { scd.indexOfEqual(c.entryPath).notNil }) {
			views[\entry].value = scd.indexOfEqual(c.entryPath)
		};
		this.setConversation(c.conversation.collect { |m| this.conversationLine(m) }.join("\n\n"));
		views[\plan].string = if(c.proposal.isNil) { "No proposal yet." } { MBGuiFormat.planText(c.proposal) };
		views[\duration].value = c.renderSettings[\duration];
		views[\sampleRate].value = ["44100", "48000", "96000"].indexOfEqual(c.renderSettings[\sampleRate].asString) ? 1;
		views[\channels].value = ["1", "2"].indexOfEqual(c.renderSettings[\numChannels].asString) ? 1;
		views[\diff].string = if(c.proposal.isNil) { "" } {
			this.proposalHeader ++ MBGuiFormat.diffText(c.proposal[\edits])
		};
		views[\send].enabled = working.not;
		views[\approve].enabled = idle and: { c.proposalState == \pending };
		views[\reject].enabled = idle and: { c.proposalState == \pending };
		views[\undo].enabled = working.not and: { project.notNil };
		views[\render].enabled = working.not and: { project.notNil } and: { scd.notEmpty };
		views[\renderResult].string = MBGuiFormat.renderText(c.renderResult, project !? { project[\root] });
		views[\renderResult].toolTip = c.renderResult !? { |r| r[\path].asString } ? "";
		views[\play].enabled = c.renderResult.notNil and: { c.isPlaying.not };
		views[\reveal].enabled = c.renderResult.notNil;
		views[\stopPlay].enabled = c.isPlaying;
		views[\stopAudition].enabled = c.isPlaying;
		views[\usageLast].string = "Last request: " ++ MBGuiFormat.usageLine(c.lastUsage);

		views[\varStart].enabled = working.not;
		views[\varStop].enabled = variation[\running] == true;
		views[\varStatus].string = variation[\status] ? "Not started.";
		this.setItems(\candidates, candidates.collect { |cand, i| MBGuiFormat.candidateLine(cand, i) }.asArray);
		this.refreshCandidateReview;
		views[\audition].enabled = candidates.notEmpty;
		views[\applyCandidate].enabled = candidates.notEmpty and: { working.not } and: { variation[\session].notNil };
		views[\renderCandidate].enabled = candidates.notEmpty and: { working.not } and: { variation[\session].notNil };

		keyProviderIds.do { |id|
			var key = { |name| (name ++ "_" ++ id).asSymbol };
			var keyWorking = #[\saving, \removing, \validating].includes(c.keyStatus[id]);
			views[key.("keyStatus")].string = c.keyStatusText(id);
			views[key.("keySave")].enabled = keyWorking.not;
			views[key.("keyRemove")].enabled = keyWorking.not and: { #[\stored, \valid, \invalid].includes(c.keyStatus[id]) };
			views[key.("keyValidate")].enabled = keyWorking.not and: { #[\stored, \valid, \invalid].includes(c.keyStatus[id]) };
		};

		views[\usageLastDetail].string = MBGuiFormat.usageLine(c.lastUsage);
		views[\usageSession].string = MBGuiFormat.totalsLine(c.sessionTotals);
		this.setItems(\history, c.history.collect { |r| MBGuiFormat.usageLine(r) }.asArray);
		views[\clearHistory].enabled = c.history.notEmpty;
		refreshing = false;
	}

	// Qt reports every widget of an unshown window as invisible, so the
	// intended visibility is tracked for tests and drivers.
	setShown { |key, flag|
		shown[key] = flag;
		views[key].visible = flag;
	}

	refreshCandidateReview {
		var index = views[\candidates].value;
		var candidate = if(index.isKindOf(Integer)) { controller.variation[\candidates][index] };
		var proposal = candidate !? { candidate[\proposal] }, code = candidate !? { candidate[\code] };
		views[\candidateReview].string = if(candidate.isNil) { "Select a candidate to review its code." } {
			(if(proposal.notNil) {
				MBGuiFormat.planText(proposal) ++ "\n\n" ++ MBGuiFormat.diffText(proposal[\edits] ? [])
			} { candidate[\summary] ? "" })
			++ "\n\nFull candidate code:\n"
			++ (if(code.notNil) { code.keys.asArray.sort.collect { |path|
				path.asString ++ "\n" ++ code[path].asString
			}.join("\n\n") } { "No code available." })
		};
	}

	isShown { |key| ^shown[key] == true }

	// Keeps the newest message visible.
	setConversation { |text|
		var view = views[\conversation];
		if(view.string != text) {
			view.string = text;
			view.select(text.size, 0);
		};
	}

	// Replacing items clears the selection, so only replace changed lists.
	setItems { |key, items|
		if((views[key].items ? []) != items) { views[key].items = items };
	}

	refreshDJ {
		var c = controller;
		var items, current, models = c.models;
		views[\provider].items = c.providers.collect { |p| MBGuiFormat.providerLabel(p) };
		current = c.providers.detectIndex { |p| p[\id] == c.providerId };
		if(current.notNil) { views[\provider].value = current };

		items = models.collect { |m| MBGuiFormat.modelLabel(m) };
		modelItemIds = models.collect { |m| m[\id].asString };
		current = modelItemIds.indexOfEqual(c.modelId);
		if(current.isNil) {
			items = [if(c.modelId.isNil) { "— choose a model —" } {
				c.modelId ++ " [UNAVAILABLE: not in the model list]"
			}] ++ items;
			modelItemIds = [nil] ++ modelItemIds;
			current = 0;
		};
		views[\model].items = items;
		views[\model].value = current;
		views[\provider].enabled = c.isWorking.not;
		views[\model].enabled = c.isWorking.not;
		views[\refreshModels].enabled = c.providerId.notNil and: { c.modelRefreshing.not };
		views[\djIds].string = "Provider id: " ++ (c.providerId ? "none")
			++ "   Model id: " ++ (c.modelId ? "none selected")
			++ (if(c.modelRefreshing) { "   (refreshing...)" } { "" });
		views[\modelMessage].string = c.modelMessage ? "";
	}

	proposalHeader {
		var p = controller.proposal;
		var state = switch(controller.proposalState,
			\pending, { "PENDING REVIEW: nothing has been written yet." },
			\applied, { "APPLIED after your approval." },
			\rejected, { "REJECTED: nothing was written." },
			\noEdits, { "No file changes proposed." },
			{ "" });
		^state ++ "\n" ++ (p[\summary] !? { |s| s ++ "\n" } ? "") ++ "\n"
	}

	conversationLine { |message|
		^switch(message[\role],
			\user, { "You: " },
			\assistant, { "DJ (" ++ message[\provider] ++ " / " ++ message[\model] ++ "): " },
			\error, { "" },
			{ "-- " }
		) ++ message[\text]
	}
}
