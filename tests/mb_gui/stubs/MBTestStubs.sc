// Test-only stand-ins that implement the worker-01/worker-02 interfaces from
// docs/design/CONTRACT.md under distinct names, so MaxxedBeats.services can
// be exercised through a lookup without the real classes. Never installed.

MBTestStubLog {
	classvar <calls;
	*reset { calls = List.new }
	*add { |...args| if(calls.isNil) { this.reset }; calls.add(args) }
	*of { |op| ^(calls ? []).select { |c| c[0] == op } }
}

MBTestStubProvider {
	var <id, <displayName;
	*new { |id, displayName| ^super.newCopyArgs(id, displayName) }
}

MBTestStubProviderRegistry {
	classvar instance;
	var <providers;
	*default { ^instance ?? { instance = super.new.init } }
	init {
		providers = [
			MBTestStubProvider(\openai, "OpenAI"),
			MBTestStubProvider(\anthropic, "Anthropic"),
			MBTestStubProvider(\mock, "Mock provider")
		];
	}
	at { |id| ^providers.detect { |p| p.id == id.asSymbol } }
}

MBTestStubCredentialStore {
	*default { ^this.new }
	hasKey { |id, onResult| MBTestStubLog.add(\hasKey, id); onResult.value(id == \openai) }
	storeKey { |id, key, onSuccess, onFailure| MBTestStubLog.add(\storeKey, id, key.size); onSuccess.value }
	removeKey { |id, onSuccess, onFailure| MBTestStubLog.add(\removeKey, id); onSuccess.value }
	validateKey { |id, onSuccess, onFailure|
		MBTestStubLog.add(\validateKey, id);
		onFailure.value(MBError(\auth, "invalid key"))
	}
}

MBTestStubModelCatalog {
	var selected;
	*default { ^this.new }
	refresh { |id, onSuccess, onFailure| MBTestStubLog.add(\refresh, id); onSuccess.value(this.models(id)) }
	models { |id|
		^[(id: "stub-model", displayName: "Stub model", provider: id, usable: true, note: "")]
	}
	lastRefreshed { |id| ^"2026-10-06" }
	isStale { |id| ^false }
	selectedModel { |id|
		var chosen = if(selected.notNil) { selected[id] };
		^chosen ?? { if(id == \mock) { "stub-model" } }
	}
	selectModel { |id, modelId|
		MBTestStubLog.add(\selectModel, id, modelId);
		selected = selected ?? { IdentityDictionary.new };
		selected[id] = modelId;
	}
}

MBTestStubUsageMeter {
	*default { ^this.new }
	sessionTotals { ^(requests: 0) }
	history { ^[] }
	clearHistory { MBTestStubLog.add(\clearHistory) }
}

MBTestStubProject {
	var <root;
	*open { |dir|
		if(dir == "/missing") { MBError(\io, "project folder not found").throw };
		^super.newCopyArgs(dir)
	}
	files { ^["main.scd", "notes.txt"] }
	apply { |proposal, confirmed, onSuccess, onFailure|
		MBTestStubLog.add(\apply, confirmed);
		onSuccess.value(true)
	}
	undo { |onSuccess, onFailure| MBTestStubLog.add(\undo); onSuccess.value(true) }
}

MBTestStubAgent {
	var <project, <provider, <catalog, <meter;
	*new { |project, provider, catalog, meter|
		MBTestStubLog.add(\agentNew, provider.id, meter.class.name);
		^super.newCopyArgs(project, provider, catalog, meter)
	}
	propose { |userPrompt, context, onSuccess, onFailure|
		MBTestStubLog.add(\propose, userPrompt, context);
		onSuccess.value((plan: "stub plan", summary: "stub summary", edits: [], usage: nil, raw: ""));
		^MBTestStubHandle(\propose)
	}
}

MBTestStubHandle {
	var <op;
	*new { |op| ^super.newCopyArgs(op) }
	cancel { MBTestStubLog.add(\cancel, op) }
}

MBTestStubRenderer {
	*render { |project, entryPath, settings, approved, onProgress, onSuccess, onFailure|
		MBTestStubLog.add(\render, entryPath, approved, settings[\duration]);
		onProgress.value(0.5);
		onSuccess.value((path: "/stub/renders/a.wav", duration: settings[\duration]));
		^MBTestStubHandle(\render)
	}
}

MBTestStubVariationSession {
	var <agent, <project, <maxCandidates;
	*new { |agent, project, maxCandidates = 4|
		MBTestStubLog.add(\sessionNew, maxCandidates);
		^super.newCopyArgs(agent, project, maxCandidates)
	}
	start { |prompt, onCandidate, onDone, onFailure|
		MBTestStubLog.add(\sessionStart, prompt);
		onCandidate.value((seed: 1, summary: "stub candidate"));
	}
	stop { MBTestStubLog.add(\sessionStop) }
	candidates { ^[] }
	apply { |index, confirmed, onSuccess, onFailure|
		MBTestStubLog.add(\sessionApply, index, confirmed);
		onSuccess.value(true)
	}
}
