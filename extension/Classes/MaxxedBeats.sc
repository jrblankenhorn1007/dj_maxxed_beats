// SCIDE entry point of the MaxxedBeats AI music assistant:
//   MaxxedBeats.gui;
// `services` is the only place where the GUI is wired to the provider and
// workflow classes (docs/design/CONTRACT.md). Classes are looked up by name
// so this file compiles even when an optional layer is not installed.

MaxxedBeats {
	classvar <current;

	*gui { |services|
		var controller;
		if(current.notNil and: { current.isClosed.not }) {
			if(services.isNil) { current.front; ^current };
			current.close;
		};
		services = services ?? {
			var error, wired;
			try { wired = this.services } { |e| error = e };
			wired ?? { this.unavailableServices(error) }
		};
		controller = MBGuiController(services);
		current = MBGuiWindow(controller);
		controller.start;
		current.front;
		^current
	}

	*clearCurrent { current = nil }

	// Builds the service port used by MBGuiController from the contract
	// classes. `lookup` maps a class name Symbol to a class (tests pass stubs).
	*services { |lookup|
		var names = #[\MBProviderRegistry, \MBCredentialStore, \MBModelCatalog, \MBUsageMeter,
			\MBProject, \MBAgent, \MBRenderer, \MBVariationSession];
		var classes = IdentityDictionary.new, missing, instance;
		var registry, store, catalog, meter, agentFor;
		lookup = lookup ? { |name| name.asClass };
		names.do { |name| classes[name] = lookup.value(name) };
		missing = names.select { |name| classes[name].isNil };
		if(missing.notEmpty) {
			MBError(\config, "MaxxedBeats is not completely installed; missing classes: "
				++ missing.join(", ") ++ ". Re-run scripts/install_maxxedbeats.py, then recompile the class library.").throw
		};
		instance = { |name| var cls = classes[name]; if(cls.respondsTo(\default)) { cls.default } { cls.new } };
		registry = instance.(\MBProviderRegistry);
		store = instance.(\MBCredentialStore);
		catalog = instance.(\MBModelCatalog);
		meter = instance.(\MBUsageMeter);
		agentFor = { |project, providerId| classes[\MBAgent].new(project, registry.at(providerId), catalog, meter) };

		^(
			providers: {
				registry.providers.collect { |p|
					(id: p.id.asSymbol, displayName: p.displayName.asString, requiresKey: p.id.asSymbol != \mock)
				}
			},
			hasKey: { |id, onResult| store.hasKey(id, onResult) },
			storeKey: { |id, key, onSuccess, onFailure| store.storeKey(id, key, onSuccess, onFailure) },
			removeKey: { |id, onSuccess, onFailure| store.removeKey(id, onSuccess, onFailure) },
			validateKey: { |id, onSuccess, onFailure| store.validateKey(id, onSuccess, onFailure) },
			refreshModels: { |id, onSuccess, onFailure| catalog.refresh(id, onSuccess, onFailure) },
			models: { |id| catalog.models(id) },
			lastRefreshed: { |id| catalog.lastRefreshed(id) },
			isStale: { |id| catalog.isStale(id) },
			selectedModel: { |id| catalog.selectedModel(id) },
			selectModel: { |id, modelId| catalog.selectModel(id, modelId) },
			sessionTotals: { meter.sessionTotals },
			history: { meter.history },
			clearHistory: { meter.clearHistory },
			openProject: { |dir, onSuccess, onFailure|
				var project, error;
				try { project = classes[\MBProject].open(dir) } { |e| error = e };
				if(error.notNil) { onFailure.value(error) } {
					onSuccess.value((root: project.root, files: project.files, project: project))
				}
			},
			projectFiles: { |project| project.files },
			propose: { |project, providerId, modelId, prompt, context, onSuccess, onFailure|
				// The request must use exactly the model shown in the window.
				if(catalog.selectedModel(providerId).asString != modelId.asString) {
					onFailure.value(MBError(\unavailableModel, "The selected " ++ providerId
						++ " model changed; choose your DJ again before sending."));
					nil
				} {
					agentFor.(project, providerId).propose(prompt, context, onSuccess, onFailure)
				}
			},
			apply: { |project, proposal, confirmed, onSuccess, onFailure|
				project.apply(proposal, confirmed, onSuccess, onFailure)
			},
			undo: { |project, onSuccess, onFailure| project.undo(onSuccess, onFailure) },
			render: { |project, entryPath, settings, approved, onProgress, onSuccess, onFailure|
				classes[\MBRenderer].render(project, entryPath, settings, approved, onProgress, onSuccess, onFailure)
			},
			startVariations: { |project, providerId, modelId, prompt, maxCandidates, onCandidate, onDone, onFailure|
				var session;
				if(catalog.selectedModel(providerId).asString != modelId.asString) {
					onFailure.value(MBError(\unavailableModel, "The selected " ++ providerId
						++ " model changed; choose your DJ again before starting."));
					nil
				} {
					session = classes[\MBVariationSession].new(agentFor.(project, providerId), project, maxCandidates);
					session.start(prompt, onCandidate, onDone, onFailure);
					session
				}
			},
			stopVariations: { |session| session !? { session.stop } },
			applyVariation: { |session, index, confirmed, onSuccess, onFailure|
				session.apply(index, confirmed, onSuccess, onFailure)
			},
			cancel: { |handle| handle !? { handle.cancel } },
			play: { |path, onStarted, onDone, onFailure| MBGuiAudition.play(path, onStarted, onDone, onFailure) },
			stopPlayback: { |handle| handle !? { handle.stop } },
			reveal: { |path| MBGuiAudition.reveal(path) }
		)
	}

	// A port whose every operation reports `error`, so the window still opens
	// and explains what is missing instead of failing silently.
	*unavailableServices { |error|
		var failure = MBGuiFormat.asError(error ?? { MBError(\config, "MaxxedBeats services are unavailable.") });
		var fail = { |...args| var onFailure = args.reverse.detect(_.isFunction); onFailure.value(failure); nil };
		var throw = { failure.throw };
		^(
			providers: throw, models: { [] }, lastRefreshed: { nil }, isStale: { false },
			selectedModel: { nil }, selectModel: throw, hasKey: { |id, onResult| onResult.value(false) },
			storeKey: fail, removeKey: fail, validateKey: fail, refreshModels: fail,
			sessionTotals: { nil }, history: { [] }, clearHistory: throw,
			openProject: fail, propose: fail, apply: fail, undo: fail, render: fail,
			startVariations: fail, stopVariations: { nil }, applyVariation: fail,
			cancel: { nil }, play: fail, stopPlayback: { nil }, reveal: { nil }
		)
	}
}
