// Per-provider model lists (refreshed with each provider's model-list API,
// cached in model-catalog.json) and the user's per-provider model selection
// (providers.json). Both live in the non-secret settings directory.
//
// The catalog never substitutes a model: selecting an unknown or unusable
// model, or a selection that has disappeared from the provider's list, is
// reported as MBError(\unavailableModel). A cached list is stale when the
// last refresh failed or it is older than maxAgeSeconds.
MBModelCatalog {
	classvar default;
	var <registry, <settingsPath, <cachePath, <>maxAgeSeconds = 86400, clock;
	var cache, selections, lastErrors;

	*default { ^default ?? { default = this.new } }

	*new { |registry, settingsDir, clock|
		^super.new.prInit(registry, settingsDir, clock)
	}

	prInit { |argRegistry, settingsDir, argClock|
		var dir = settingsDir ?? { MBProviderPaths.settingsDir };
		registry = argRegistry ?? { MBProviderRegistry.default };
		clock = argClock ?? { { Date.getDate.rawSeconds } };
		settingsPath = dir +/+ "providers.json";
		cachePath = dir +/+ "model-catalog.json";
		lastErrors = IdentityDictionary.new;
		this.prLoad;
	}

	refresh { |id, onSuccess, onFailure|
		var provider = registry.at(id), key;
		if(provider.isNil) {
			{ onFailure.value(MBError(\config, "Unknown provider: " ++ id.asString)) }.defer;
			^nil
		};
		key = provider.id;
		^provider.listModels({ |models|
			cache[key] = (refreshedAt: clock.value, models: models.collect { |m| this.prNormalize(m, key) });
			lastErrors.removeAt(key);
			this.prSaveCache;
			onSuccess.value(this.models(key));
		}, { |error|
			lastErrors[key] = error;
			onFailure.value(error);
		})
	}

	models { |id|
		var entry = cache[id.asSymbol];
		^if(entry.isNil) { [] } { entry[\models].collect(_.copy) }
	}

	usableModels { |id| ^this.models(id).select { |m| m[\usable] } }

	lastRefreshed { |id| ^cache[id.asSymbol] !? { |entry| entry[\refreshedAt] } }

	lastError { |id| ^lastErrors[id.asSymbol] }

	isStale { |id|
		var refreshed = this.lastRefreshed(id);
		if(refreshed.isNil) { ^false };
		^lastErrors[id.asSymbol].notNil or: { (clock.value - refreshed) > maxAgeSeconds }
	}

	selectedModel { |id| ^selections[id.asSymbol] }

	// Returns nil on success or an MBError (nothing is changed on error).
	selectModel { |id, modelId|
		var error = this.prCheck(id, modelId);
		if(error.notNil) { ^error };
		selections[id.asSymbol] = modelId.asString;
		^this.prSaveSelections
	}

	// nil when the persisted selection is in the current list and usable;
	// otherwise MBError(\unavailableModel). Never changes the selection.
	checkSelection { |id|
		var selected = this.selectedModel(id);
		if(selected.isNil) {
			^MBError(\unavailableModel, "No model is selected for " ++ this.prName(id)
				++ "; refresh the model list and choose one")
		};
		^this.prCheck(id, selected)
	}

	prCheck { |id, modelId|
		var model;
		if(registry.at(id).isNil) { ^MBError(\config, "Unknown provider: " ++ id.asString) };
		if(modelId.isNil or: { modelId.asString.isEmpty }) {
			^MBError(\unavailableModel, "No model given for " ++ this.prName(id))
		};
		model = this.models(id).detect { |m| m[\id] == modelId.asString };
		if(model.isNil) {
			^MBError(\unavailableModel, "Model " ++ modelId ++ " is not in the "
				++ this.prName(id) ++ " model list" ++ if(this.lastRefreshed(id).isNil) {
					" (refresh the list first)" } { "" })
		};
		if(model[\usable] != true) {
			^MBError(\unavailableModel, "Model " ++ modelId ++ " cannot be used by this assistant: "
				++ (model[\note] ? "unsupported"))
		};
		^nil
	}

	prName { |id| ^registry.at(id) !? (_.displayName) ? id.asString }

	prNormalize { |model, key|
		^(id: model[\id].asString, displayName: (model[\displayName] ? model[\id]).asString,
			provider: key, usable: model[\usable] == true, note: (model[\note] ? "").asString)
	}

	prLoad {
		var json = MBProviderPaths.readJSON(cachePath), settings, providers;
		cache = IdentityDictionary.new;
		selections = IdentityDictionary.new;
		providers = if(json.isKindOf(Dictionary)) { json["providers"] };
		if(providers.isKindOf(Dictionary)) {
			providers.keysValuesDo { |key, entry|
				if(entry.isKindOf(Dictionary) and: { entry["models"].isKindOf(SequenceableCollection) }) {
					cache[key.asSymbol] = (refreshedAt: entry["refreshedAt"],
						models: entry["models"].select(_.isKindOf(Dictionary)).collect { |m|
							this.prNormalize((id: m["id"], displayName: m["displayName"],
								usable: m["usable"], note: m["note"]), key.asSymbol)
						});
				}
			}
		};
		settings = MBProviderPaths.readJSON(settingsPath);
		if(settings.isKindOf(Dictionary) and: { settings["selectedModels"].isKindOf(Dictionary) }) {
			settings["selectedModels"].keysValuesDo { |key, value|
				if(value.isString) { selections[key.asSymbol] = value }
			}
		};
	}

	prSaveCache {
		var providers = Dictionary.new;
		cache.keysValuesDo { |key, entry| providers[key.asString] = entry };
		^MBProviderPaths.writeJSON(cachePath, (schema: 1, providers: providers))
	}

	prSaveSelections {
		var current = MBProviderPaths.readJSON(settingsPath), chosen = Dictionary.new;
		if(current.isKindOf(Dictionary).not) { current = Dictionary.new };
		selections.keysValuesDo { |key, value| chosen[key.asString] = value };
		current["schema"] = 1;
		current["selectedModels"] = chosen;
		^MBProviderPaths.writeJSON(settingsPath, current)
	}
}
