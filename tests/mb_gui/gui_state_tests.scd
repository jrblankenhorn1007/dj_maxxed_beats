// Headless state tests for the MaxxedBeats agent window (run by
// tests/test_mb_gui.py). Each case builds the real Qt window around
// MBGuiController with fake services, drives the actual widgets'
// actions, and asserts controller/view state. Output lines:
//   MBTEST PASS <case>/<check>    MBTEST FAIL <case>/<check> :: <detail>
//   MBTEST DONE passes=<n> failures=<n>
(
var here = thisProcess.nowExecutingPath.dirname;
var makeFakes = (here +/+ "fake_services.scd").load;
var passes = 0, failures = 0, caseName = "";
var cases = List.new;
var check = { |label, condition, detail|
	if(condition == true) {
		passes = passes + 1;
		("MBTEST PASS " ++ caseName ++ "/" ++ label).postln;
	} {
		failures = failures + 1;
		("MBTEST FAIL " ++ caseName ++ "/" ++ label ++ " :: " ++ (detail ? "")).postln;
	};
};
var build = { |setup|
	var f = makeFakes.value;
	var c, w;
	setup.value(f);
	c = MBGuiController(f[\services]);
	w = MBGuiWindow(c);
	c.start;
	(f: f, c: c, w: w, v: w.views)
};
var press = { |t, key| t[\v][key].doAction };
var popupIndex = { |view, substring|
	view.items.detectIndex { |item| item.asString.contains(substring) }
};
var chooseProvider = { |t, id|
	var view = t[\v][\provider];
	view.valueAction = popupIndex.(view, "(" ++ id ++ ")");
};
var openProject = { |t|
	t[\v][\projectPath].string = "/fake/project";
	press.(t, \openProject);
};
var ready = { |t|
	openProject.(t);
	chooseProvider.(t, \mock);
	t[\v][\prompt].string = "Make a warm techno groove";
};
var allText = { |t|
	t[\v].values.collect { |view|
		var text = "";
		if(view.respondsTo(\string)) { text = text ++ view.string.asString };
		if(view.respondsTo(\items)) { text = text ++ (view.items ? []).join("\n") };
		text
	}.join("\n")
};
var errorKind = { |t| t[\c].error !? { |e| e.kind } };
var calls = { |t, op| t[\f].callsOf(op) };
var addCase = { |name, body, setup| cases.add([name, body, setup]) };

addCase.(\windowBuilds, { |t|
	check.(\djLabel, t[\v][\djLabel].string == "Choose your DJ", t[\v][\djLabel].string);
	check.(\title, t[\w].window.name.contains("MaxxedBeats"));
	check.(\providerItems, t[\v][\provider].items.includesEqual("OpenAI (openai)")
		and: { t[\v][\provider].items.includesEqual("Mock DJ (mock)") }, t[\v][\provider].items.cs);
	check.(\tabs, [\tabCompose, \tabVariations, \tabKeys, \tabUsage].every { |k| t[\v][k].notNil });
	check.(\privacy, t[\v][\privacyNotice].string.contains("credential store")
		and: { t[\v][\privacyNotice].string.contains("charges") });
	check.(\noErrorAtStart, t[\c].error.isNil, t[\c].error.cs);
	check.(\noRequests, calls.(t, \propose).isEmpty and: { calls.(t, \render).isEmpty });
	check.(\keysChecked, calls.(t, \hasKey).collect { |c| c[1] }.asSet == Set[\openai, \anthropic]);
});

addCase.(\explicitProviderAndModelIds, { |t|
	chooseProvider.(t, \mock);
	check.(\provider, t[\c].providerId == \mock);
	check.(\model, t[\c].modelId == "mock-dj-1", t[\c].modelId.cs);
	check.(\idsShown, t[\v][\djIds].string.contains("mock")
		and: { t[\v][\djIds].string.contains("mock-dj-1") }, t[\v][\djIds].string);
	check.(\modelItemsShowIds, t[\v][\model].items.any { |i| i.contains("mock-dj-1") });
	check.(\unusableLabelled, t[\v][\model].items.any { |i|
		i.contains("mock-dj-retired") and: { i.contains("unavailable") } }, t[\v][\model].items.cs);
});

addCase.(\selectingUsableModelPersistsPerProvider, { |t|
	chooseProvider.(t, \openai);
	check.(\noModelYet, t[\c].modelId.isNil);
	t[\v][\model].valueAction = popupIndex.(t[\v][\model], "gpt-test-1");
	check.(\selected, t[\c].modelId == "gpt-test-1");
	check.(\persisted, calls.(t, \selectModel).any { |c| c[1] == \openai and: { c[2] == "gpt-test-1" } });
	chooseProvider.(t, \mock);
	check.(\mockKeepsOwn, t[\c].modelId == "mock-dj-1");
});

addCase.(\noSilentFallbackForMissingModel, { |t|
	ready.(t);
	check.(\keepsSelection, t[\c].modelId == "mock-dj-gone", t[\c].modelId.cs);
	check.(\labelled, t[\v][\model].items[t[\v][\model].value].contains("mock-dj-gone")
		and: { t[\v][\model].items[t[\v][\model].value].contains("UNAVAILABLE") }, t[\v][\model].items.cs);
	check.(\message, t[\v][\modelMessage].string.contains("never switches"), t[\v][\modelMessage].string);
	press.(t, \send);
	check.(\blocked, errorKind.(t) == \unavailableModel, errorKind.(t).cs);
	check.(\noRequest, calls.(t, \propose).isEmpty);
	check.(\noSubstitution, calls.(t, \selectModel).isEmpty);
}, { |f| f[\selected][\mock] = "mock-dj-gone" });

addCase.(\unusableModelRefused, { |t|
	chooseProvider.(t, \mock);
	t[\v][\model].valueAction = popupIndex.(t[\v][\model], "mock-dj-retired");
	check.(\error, errorKind.(t) == \unavailableModel);
	check.(\unchanged, t[\c].modelId == "mock-dj-1");
	check.(\notPersisted, calls.(t, \selectModel).isEmpty);
});

addCase.(\modelRefresh, { |t|
	chooseProvider.(t, \openai);
	t[\f][\refreshResult][\openai] = [
		(id: "gpt-test-1", displayName: "GPT Test 1", provider: \openai, usable: true, note: ""),
		(id: "gpt-test-2", displayName: "GPT Test 2", provider: \openai, usable: true, note: "")
	];
	press.(t, \refreshModels);
	check.(\called, calls.(t, \refreshModels).any { |c| c[1] == \openai });
	check.(\listed, t[\v][\model].items.any { |i| i.contains("gpt-test-2") }, t[\v][\model].items.cs);
	check.(\refreshedShown, t[\v][\modelMessage].string.contains("2026-10-06 21:30")
		or: { t[\v][\djIds].string.contains("2026-10-06 21:30") }, t[\v][\modelMessage].string);
	check.(\noError, t[\c].error.isNil);
});

addCase.(\modelRefreshFailureKeepsStaleList, { |t|
	chooseProvider.(t, \mock);
	t[\f][\failures][\refreshModels] = MBError(\network, "connection refused");
	press.(t, \refreshModels);
	check.(\error, errorKind.(t) == \network);
	check.(\errorShown, t[\v][\error].string.contains("network"), t[\v][\error].string);
	check.(\stale, t[\v][\modelMessage].string.contains("stale"), t[\v][\modelMessage].string);
	check.(\cachedKept, t[\v][\model].items.any { |i| i.contains("mock-dj-1") });
	check.(\selectionKept, t[\c].modelId == "mock-dj-1");
});

addCase.(\keyEntryMaskedAndNeverEchoed, { |t|
	var secret = "sk-test-SECRET1234567890";
	var mask = t[\w].masks[\openai];
	t[\v][\keyField_openai].string = secret;
	mask.sync;
	check.(\fieldCleared, t[\v][\keyField_openai].string == "", t[\v][\keyField_openai].string);
	check.(\maskedDisplay, t[\v][\keyMask_openai].string.contains("*")
		and: { t[\v][\keyMask_openai].string.contains("SECRET").not }, t[\v][\keyMask_openai].string);
	check.(\noEchoBeforeSave, allText.(t).contains("SECRET").not);
	press.(t, \keySave_openai);
	check.(\stored, t[\f][\keys][\openai] == secret);
	check.(\status, t[\c].keyStatus[\openai] == \stored, t[\c].keyStatus[\openai].cs);
	check.(\maskCleared, mask.secret.size == 0);
	check.(\noEchoAfterSave, allText.(t).contains("SECRET").not);
	check.(\notInCalls, t[\f][\calls].cs.contains("SECRET").not);
	check.(\notInController, t[\c].conversation.cs.contains("SECRET").not and: { t[\c].status.contains("SECRET").not });
});

addCase.(\keyTypingAndBackspace, { |t|
	var mask = t[\w].masks[\openai];
	"sk-ab".do { |char| t[\v][\keyField_openai].string = char.asString; mask.sync };
	check.(\typed, mask.secret == "sk-ab", mask.secret.size.asString);
	mask.backspace;
	check.(\backspace, mask.secret == "sk-a");
	press.(t, \keyClear_openai);
	check.(\cleared, mask.secret.size == 0 and: { t[\v][\keyMask_openai].string.contains("*").not });
});

addCase.(\keyStoreFailureRedacted, { |t|
	var secret = "sk-test-SECRET1234567890";
	t[\f][\failures][\storeKey] = MBError(\io, "keychain rejected " ++ secret);
	t[\v][\keyField_openai].string = secret;
	t[\w].masks[\openai].sync;
	press.(t, \keySave_openai);
	check.(\error, errorKind.(t) == \io);
	check.(\redacted, t[\c].error.detail.contains("SECRET").not
		and: { t[\c].error.detail.contains("[redacted]") }, t[\c].error.detail);
	check.(\notShown, allText.(t).contains("SECRET").not);
	check.(\notStored, t[\c].keyStatus[\openai] == \missing, t[\c].keyStatus[\openai].cs);
});

addCase.(\keyRemoveNeedsConfirmation, { |t|
	t[\f][\keys][\openai] = "sk-existing-000000";
	t[\c].checkKey(\openai);
	press.(t, \keyRemove_openai);
	check.(\confirmShown, t[\w].isShown(\confirmPanel) and: { t[\c].pendingConfirm.notNil });
	check.(\notYet, calls.(t, \removeKey).isEmpty);
	press.(t, \cancelConfirm);
	check.(\cancelled, calls.(t, \removeKey).isEmpty and: { t[\c].pendingConfirm.isNil });
	check.(\panelHidden, t[\w].isShown(\confirmPanel).not);
	press.(t, \keyRemove_openai);
	press.(t, \confirm);
	check.(\removed, calls.(t, \removeKey).size == 1 and: { t[\c].keyStatus[\openai] == \missing });
});

addCase.(\keyValidate, { |t|
	t[\f][\keys][\openai] = "sk-existing-000000";
	t[\c].checkKey(\openai);
	press.(t, \keyValidate_openai);
	check.(\valid, t[\c].keyStatus[\openai] == \valid);
	t[\f][\failures][\validateKey] = MBError(\auth, "401 invalid key");
	press.(t, \keyValidate_openai);
	check.(\invalid, t[\c].keyStatus[\openai] == \invalid and: { errorKind.(t) == \auth });
	check.(\statusShown, t[\v][\keyStatus_openai].string.contains("invalid"), t[\v][\keyStatus_openai].string);
});

addCase.(\missingKeyBlocksRequest, { |t|
	openProject.(t);
	chooseProvider.(t, \openai);
	t[\v][\model].valueAction = popupIndex.(t[\v][\model], "gpt-test-1");
	t[\v][\prompt].string = "hello";
	press.(t, \send);
	check.(\authError, errorKind.(t) == \auth);
	check.(\noRequest, calls.(t, \propose).isEmpty);
});

addCase.(\projectOpen, { |t|
	openProject.(t);
	check.(\opened, t[\c].project.notNil and: { t[\c].project[\root] == "/fake/project" });
	check.(\files, t[\v][\contextFiles].items.size == 3);
	check.(\entryScdOnly, t[\v][\entry].items == ["main.scd", "drums.scd"], t[\v][\entry].items.cs);
	check.(\label, t[\v][\projectLabel].string.contains("/fake/project"));
});

addCase.(\projectOpenFailure, { |t|
	t[\f][\failures][\openProject] = MBError(\io, "no such directory");
	openProject.(t);
	check.(\error, errorKind.(t) == \io and: { t[\c].project.isNil });
});

addCase.(\proposalFlowNothingWrittenBeforeApproval, { |t|
	var call;
	ready.(t);
	t[\v][\contextFiles].selection = [0];
	press.(t, \send);
	call = calls.(t, \propose).first;
	check.(\explicitIds, call.notNil and: { call[1] == \mock and: { call[2] == "mock-dj-1" } }, call.cs);
	check.(\onlySelectedContext, call.notNil and: { call[4][\files] == ["main.scd"] }, call.cs);
	check.(\busy, t[\c].busy == \propose and: { t[\v][\send].enabled.not });
	check.(\cancelEnabled, t[\v][\cancel].enabled);
	t[\f].succeedPropose;
	check.(\notBusy, t[\c].busy.isNil and: { t[\v][\send].enabled });
	check.(\plan, t[\v][\plan].string.contains("120 BPM"), t[\v][\plan].string);
	check.(\diff, t[\v][\diff].string.contains("+~kick = 1;")
		and: { t[\v][\diff].string.contains("main.scd") }, t[\v][\diff].string);
	check.(\conversation, t[\v][\conversation].string.contains("Make a warm techno groove")
		and: { t[\v][\conversation].string.contains("four-on-the-floor") });
	check.(\approveEnabled, t[\v][\approve].enabled and: { t[\v][\reject].enabled });
	check.(\nothingApplied, calls.(t, \apply).isEmpty and: { calls.(t, \render).isEmpty });
	check.(\usage, t[\v][\usageLast].string.contains("US$0.0123")
		and: { t[\v][\usageLast].string.contains("1.23 credits") }
		and: { t[\v][\usageLast].string.contains("mock-rates-2026-10") }
		and: { t[\v][\usageLast].string.contains("in 120") }, t[\v][\usageLast].string);
	check.(\sessionUsage, t[\v][\usageSession].string.contains("1 request"), t[\v][\usageSession].string);
	check.(\historyListed, t[\v][\history].items.size == 1);
	check.(\promptCleared, t[\v][\prompt].string == "");
});

addCase.(\approveRequiresConfirmation, { |t|
	ready.(t);
	press.(t, \send);
	t[\f].succeedPropose;
	press.(t, \approve);
	check.(\confirmShown, t[\w].isShown(\confirmPanel)
		and: { t[\v][\confirmText].string.contains("backup") }, t[\v][\confirmText].string);
	check.(\notApplied, calls.(t, \apply).isEmpty);
	press.(t, \cancelConfirm);
	check.(\stillNotApplied, calls.(t, \apply).isEmpty and: { t[\c].proposalState == \pending });
	press.(t, \approve);
	press.(t, \confirm);
	check.(\appliedConfirmed, calls.(t, \apply).size == 1 and: { calls.(t, \apply)[0][1] == true });
	t[\f].fire(\apply, 0, true);
	check.(\state, t[\c].proposalState == \applied and: { t[\v][\approve].enabled.not });
	check.(\status, t[\v][\status].string.contains("Applied"), t[\v][\status].string);
});

addCase.(\applyFailureNotSuccess, { |t|
	ready.(t);
	press.(t, \send);
	t[\f].succeedPropose;
	press.(t, \approve);
	press.(t, \confirm);
	t[\f].fire(\apply, 1, MBError(\io, "disk full"));
	check.(\error, errorKind.(t) == \io);
	check.(\stillPending, t[\c].proposalState == \pending);
	check.(\noSuccess, t[\v][\status].string.contains("Applied").not, t[\v][\status].string);
});

addCase.(\rejectWritesNothing, { |t|
	ready.(t);
	press.(t, \send);
	t[\f].succeedPropose;
	press.(t, \reject);
	check.(\rejected, t[\c].proposalState == \rejected);
	check.(\noApply, calls.(t, \apply).isEmpty);
	check.(\noPendingConfirm, t[\c].pendingConfirm.isNil);
	check.(\noted, t[\v][\conversation].string.contains("unchanged"));
});

addCase.(\pendingProposalBlocksNewPrompt, { |t|
	ready.(t);
	press.(t, \send);
	t[\f].succeedPropose;
	t[\v][\prompt].string = "another";
	press.(t, \send);
	check.(\blocked, errorKind.(t) == \validation and: { calls.(t, \propose).size == 1 });
});

addCase.(\proposeFailureShown, { |t|
	ready.(t);
	press.(t, \send);
	t[\f].fire(\propose, 1, MBError(\network, "timeout after 60 s"));
	check.(\error, errorKind.(t) == \network);
	check.(\visible, t[\w].isShown(\errorRow) and: { t[\v][\error].string.contains("timeout") });
	check.(\noProposal, t[\c].proposal.isNil and: { t[\v][\approve].enabled.not });
	check.(\conversation, t[\v][\conversation].string.contains("network"));
	press.(t, \dismissError);
	check.(\dismissed, t[\c].error.isNil and: { t[\w].isShown(\errorRow).not });
});

addCase.(\cancelIgnoresLateResult, { |t|
	ready.(t);
	press.(t, \send);
	press.(t, \cancel);
	check.(\cancelCalled, calls.(t, \cancel).size == 1 and: { t[\f][\handles][0][\cancelled] });
	check.(\notBusy, t[\c].busy.isNil);
	check.(\status, t[\v][\status].string.contains("Cancelled"), t[\v][\status].string);
	t[\f].succeedPropose;
	check.(\lateIgnored, t[\c].proposal.isNil);
});

addCase.(\renderRequiresConfirmation, { |t|
	var call;
	openProject.(t);
	t[\v][\duration].value = 4;
	press.(t, \render);
	check.(\confirmShown, t[\w].isShown(\confirmPanel)
		and: { t[\v][\confirmText].string.contains("separate") }, t[\v][\confirmText].string);
	check.(\notRendered, calls.(t, \render).isEmpty);
	press.(t, \cancelConfirm);
	check.(\stillNot, calls.(t, \render).isEmpty);
	press.(t, \render);
	press.(t, \confirm);
	call = calls.(t, \render).first;
	check.(\approved, call.notNil and: { call[3] == true }, call.cs);
	check.(\entry, call.notNil and: { call[1] == "main.scd" });
	check.(\settings, call.notNil and: { call[2][\duration] == 4 and: { call[2][\sampleRate] == 48000 }
		and: { call[2][\numChannels] == 2 } }, call.cs);
	t[\f].fire(\render, 2, 0.5);
	check.(\progress, t[\v][\status].string.contains("50%") and: { t[\c].progress == 0.5 }, t[\v][\status].string);
	check.(\noPlayYet, t[\v][\play].enabled.not);
	t[\f].fire(\render, 0, t[\f][\renderResult].value);
	check.(\result, t[\v][\renderResult].string.contains("main-20261006-001.wav")
		and: { t[\v][\renderResult].string.contains("checks OK") }, t[\v][\renderResult].string);
	check.(\playEnabled, t[\v][\play].enabled and: { t[\v][\reveal].enabled });
	press.(t, \play);
	check.(\played, calls.(t, \play).any { |c| c[1].contains("main-20261006-001.wav") });
	check.(\playing, t[\v][\stopPlay].enabled);
	press.(t, \stopPlay);
	check.(\stopped, calls.(t, \stopPlayback).size == 1 and: { t[\c].playing.isNil });
	press.(t, \reveal);
	check.(\revealed, calls.(t, \reveal).size == 1);
});

addCase.(\progressResetsOnNextOperation, { |t|
	ready.(t);
	press.(t, \render);
	press.(t, \confirm);
	t[\f].fire(\render, 0, t[\f][\renderResult].value);
	check.(\full, t[\c].progress == 1);
	press.(t, \send);
	check.(\reset, t[\c].progress.isNil);
	// Qt treats a single "&" as a mnemonic marker; the tab must escape it.
	check.(\tabLabel, t[\v][\tabKeys].states[0][0] == "Keys && Privacy");
	t[\v][\keyField_openai].string = "sk-0123456789012345678901234567890";
	t[\w].masks[\openai].sync;
	check.(\maskShort, t[\v][\keyMask_openai].string.size < 30, t[\v][\keyMask_openai].string);
});

addCase.(\renderFailureNotSuccess, { |t|
	openProject.(t);
	press.(t, \render);
	press.(t, \confirm);
	t[\f].fire(\render, 1, MBError(\render, "scsynth exited with status 1"));
	check.(\error, errorKind.(t) == \render);
	check.(\noResult, t[\c].renderResult.isNil and: { t[\v][\play].enabled.not });
	check.(\status, t[\v][\status].string.contains("failed"), t[\v][\status].string);
});

addCase.(\renderCheckWarnings, { |t|
	openProject.(t);
	press.(t, \render);
	press.(t, \confirm);
	t[\f].fire(\render, 0, t[\f][\renderResult].value((finite: true, silent: true, clipped: false, durationOk: true)));
	check.(\warning, t[\v][\renderResult].string.contains("WARNING")
		and: { t[\v][\renderResult].string.contains("silent") });
	check.(\statusWarns, t[\v][\status].string.contains("warning"), t[\v][\status].string);
});

addCase.(\renderInvalidSettings, { |t|
	openProject.(t);
	t[\v][\duration].value = 0;
	press.(t, \render);
	check.(\noConfirm, t[\c].pendingConfirm.isNil or: { t[\v][\duration].value > 0 });
});

addCase.(\usageMissingAndStaleRates, { |t|
	var proposal;
	ready.(t);
	press.(t, \send);
	proposal = t[\f][\proposal].value;
	proposal[\usage] = (provider: \mock, model: "mock-dj-1", inputTokens: 10, outputTokens: 5,
		cachedInputTokens: nil, usd: nil, credits: nil, rateStatus: \missing, rateTable: nil);
	t[\f].succeedPropose(proposal);
	check.(\unavailable, t[\v][\usageLast].string.contains("USD unavailable")
		and: { t[\v][\usageLast].string.contains("credits unavailable") }
		and: { t[\v][\usageLast].string.contains("MISSING") }, t[\v][\usageLast].string);
	check.(\neverZero, t[\v][\usageLast].string.contains("US$0.0000").not
		and: { t[\v][\usageSession].string.contains("US$0.0000").not }, t[\v][\usageSession].string);
	check.(\cachedUnknown, t[\v][\usageLast].string.contains("cached ?"));
	check.(\stale, MBGuiFormat.usageLine((usd: 0.5, credits: 50, rateStatus: \stale, rateTable: "v1"))
		.contains("STALE"));
});

addCase.(\historyClearNeedsConfirmation, { |t|
	ready.(t);
	press.(t, \send);
	t[\f].succeedPropose;
	press.(t, \clearHistory);
	check.(\notYet, calls.(t, \clearHistory).isEmpty and: { t[\w].isShown(\confirmPanel) });
	press.(t, \confirm);
	check.(\cleared, calls.(t, \clearHistory).size == 1 and: { t[\v][\history].items.isEmpty });
});

addCase.(\variationSession, { |t|
	ready.(t);
	t[\v][\varPrompt].string = "darker bassline";
	t[\v][\varMax].value = 4;
	press.(t, \varStart);
	check.(\started, calls.(t, \startVariations).any { |c| c[1] == \mock and: { c[2] == "mock-dj-1" }
		and: { c[4] == 4 } }, calls.(t, \startVariations).cs);
	check.(\running, t[\c].variation[\running] and: { t[\v][\varStop].enabled } and: { t[\v][\send].enabled.not });
	2.do { |i| t[\f].fire(\variations, 0, t[\f][\candidate].value(i)) };
	check.(\listed, t[\v][\candidates].items.size == 2, t[\v][\candidates].items.cs);
	check.(\checksShown, t[\v][\candidates].items[0].contains("checks OK"));
	check.(\count, t[\v][\varStatus].string.contains("2 of 4"), t[\v][\varStatus].string);
	press.(t, \varStop);
	check.(\stopCalled, calls.(t, \stopVariations).size == 1 and: { t[\c].variation[\running].not });
	check.(\stoppedShown, t[\v][\varStatus].string.contains("Stopped"), t[\v][\varStatus].string);
	t[\f].fire(\variations, 0, t[\f][\candidate].value(2));
	check.(\lateIgnored, t[\v][\candidates].items.size == 2);
	t[\v][\candidates].value = 1;
	press.(t, \audition);
	check.(\auditioned, calls.(t, \play).any { |c| c[1].contains("cand1.wav") });
	press.(t, \applyCandidate);
	check.(\needsConfirm, calls.(t, \applyVariation).isEmpty and: { t[\w].isShown(\confirmPanel) });
	press.(t, \confirm);
	check.(\applied, calls.(t, \applyVariation).any { |c| c[1] == 1 and: { c[2] == true } });
	t[\f].fire(\applyVariation, 0, true);
	check.(\appliedStatus, t[\v][\status].string.contains("candidate #2"), t[\v][\status].string);
});

addCase.(\variationCapEnforced, { |t|
	ready.(t);
	t[\v][\varPrompt].string = "faster";
	t[\v][\varMax].value = 2;
	press.(t, \varStart);
	3.do { |i| t[\f].fire(\variations, 0, t[\f][\candidate].value(i)) };
	check.(\capped, t[\v][\candidates].items.size == 2, t[\v][\candidates].items.cs);
	check.(\stoppedAtCap, calls.(t, \stopVariations).size == 1 and: { t[\c].variation[\running].not });
});

addCase.(\variationMaxClipped, { |t|
	ready.(t);
	t[\v][\varPrompt].string = "x";
	t[\v][\varMax].value = 10;
	press.(t, \varStart);
	check.(\clipped, calls.(t, \startVariations).first !? { |c| c[4] == 4 } ? false,
		calls.(t, \startVariations).cs);
});

addCase.(\variationDoneAndFailure, { |t|
	ready.(t);
	t[\v][\varPrompt].string = "x";
	press.(t, \varStart);
	t[\f].fire(\variations, 0, t[\f][\candidate].value(0));
	t[\f].fire(\variations, 2, MBError(\rateLimit, "429 slow down"));
	check.(\error, errorKind.(t) == \rateLimit and: { t[\c].variation[\running].not });
	check.(\kept, t[\v][\candidates].items.size == 1);
});

addCase.(\undoRequiresConfirmation, { |t|
	openProject.(t);
	press.(t, \undo);
	check.(\notYet, calls.(t, \undo).isEmpty and: { t[\w].isShown(\confirmPanel) });
	press.(t, \confirm);
	check.(\called, calls.(t, \undo).size == 1);
	t[\f].fire(\undo, 0, true);
	check.(\status, t[\v][\status].string.contains("Restored"), t[\v][\status].string);
	press.(t, \undo);
	press.(t, \confirm);
	t[\f].fire(\undo, 1, MBError(\io, "no backups"));
	check.(\failure, errorKind.(t) == \io);
});

addCase.(\switchingProviderBlockedWhileBusy, { |t|
	ready.(t);
	press.(t, \send);
	chooseProvider.(t, \openai);
	check.(\unchanged, t[\c].providerId == \mock);
	check.(\popupRestored, t[\v][\provider].items[t[\v][\provider].value].contains("(mock)"));
});

addCase.(\closeCancelsWork, { |t|
	ready.(t);
	press.(t, \send);
	t[\w].close;
	check.(\cancelled, calls.(t, \cancel).size == 1);
	t[\f].succeedPropose;
	check.(\ignored, t[\c].proposal.isNil);
});

addCase.(\formatting, { |t|
	check.(\fixed, MBGuiFormat.fixed(0.0123, 4) == "0.0123" and: { MBGuiFormat.fixed(12.5, 2) == "12.50" });
	check.(\redactBearer, MBGuiFormat.redact("Authorization: Bearer abcDEF123.xyz").contains("abcDEF123").not);
	check.(\redactHeader, MBGuiFormat.redact("x-api-key: sk-ant-api03-ZZZZZZ").contains("ZZZZZZ").not);
	check.(\redactGiven, MBGuiFormat.redact("oops plainsecretvalue", ["plainsecretvalue"]) == "oops [redacted]");
	check.(\errorText, MBGuiFormat.errorText(MBError(\parse, "bad JSON")) == "Error (parse): bad JSON");
});

// Run every case in a fresh window; the optional setup function prepares
// the fakes before the controller starts.
cases.do { |entry|
	var t;
	caseName = entry[0];
	try {
		t = build.(entry[2]);
		entry[1].value(t);
	} { |error|
		check.(\exception, false, error.errorString);
	};
	if(t.notNil) { try { t[\w].close } };
};
("MBTEST DONE passes=" ++ passes ++ " failures=" ++ failures).postln;
0.exit;
)
