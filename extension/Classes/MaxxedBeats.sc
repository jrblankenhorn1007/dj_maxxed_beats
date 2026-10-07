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
			var wired = MBWorkflowTry.value({ this.services });
			if(wired.isKindOf(Exception)) { this.unavailableServices(wired) } { wired }
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
	// `overrides` may supply instances: (store:, registry:, catalog:, meter:);
	// a store override also builds a registry and catalog that use it.
	*services { |lookup, overrides|
		var names = #[\MBProviderRegistry, \MBCredentialStore, \MBModelCatalog, \MBUsageMeter,
			\MBProject, \MBAgent, \MBRenderer, \MBVariationSession];
		var classes = IdentityDictionary.new, missing, instance;
		var registry, store, catalog, meter, agentFor, sameModel;
		lookup = lookup ? { |name| name.asClass };
		overrides = overrides ? ();
		names.do { |name| classes[name] = lookup.value(name) };
		missing = names.select { |name| classes[name].isNil };
		if(missing.notEmpty) {
			MBError(\config, "MaxxedBeats is not completely installed; missing classes: "
				++ missing.join(", ") ++ ". Re-run the MaxxedBeats installer (install.ps1 from MaxxedBeats-Windows-x64.zip on Windows, or scripts/install_maxxedbeats.py), then recompile the class library.").throw
		};
		instance = { |name| var cls = classes[name]; if(cls.respondsTo(\default)) { cls.default } { cls.new } };
		store = overrides[\store];
		registry = overrides[\registry] ?? {
			if(store.notNil) { classes[\MBProviderRegistry].new(store) } { instance.(\MBProviderRegistry) }
		};
		store = store ?? { if(registry.respondsTo(\store)) { registry.store } } ?? { instance.(\MBCredentialStore) };
		catalog = overrides[\catalog] ?? {
			if(overrides[\registry].notNil or: { overrides[\store].notNil }) {
				classes[\MBModelCatalog].new(registry)
			} { instance.(\MBModelCatalog) }
		};
		meter = overrides[\meter] ?? { instance.(\MBUsageMeter) };
		agentFor = { |project, providerId| classes[\MBAgent].new(project, registry.at(providerId), catalog, meter) };
		// Requests must use exactly the model shown in the window.
		sameModel = { |providerId, modelId, onFailure|
			var same = catalog.selectedModel(providerId).asString == modelId.asString;
			if(same.not) {
				onFailure.value(MBError(\unavailableModel, "The selected " ++ providerId
					++ " model changed; choose your DJ again."))
			};
			same
		};

		^(
			providers: {
				registry.providers.collect { |p|
					(id: p.id.asSymbol, displayName: p.displayName.asString,
						requiresKey: #[\mock, \copilot].includes(p.id.asSymbol).not)
				}
			},
			hasKey: { |id, onResult| store.hasKey(id, onResult) },
			storeKey: { |id, key, onSuccess, onFailure| store.storeKey(id, key, onSuccess, onFailure) },
			removeKey: { |id, onSuccess, onFailure| store.removeKey(id, onSuccess, onFailure) },
			validateKey: { |id, onSuccess, onFailure| store.validateKey(id, onSuccess, onFailure, registry.at(id)) },
			loginCopilot: { |onSuccess, onFailure| registry.at(\copilot).login(onSuccess, onFailure) },
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
				var project = MBWorkflowTry.value({ classes[\MBProject].open(dir) });
				if(project.isKindOf(Exception)) { onFailure.value(project) } {
					onSuccess.value((root: project.root, files: project.files, project: project))
				}
			},
			projectFiles: { |project| project.files },
			propose: { |project, providerId, modelId, prompt, context, onSuccess, onFailure|
				if(sameModel.(providerId, modelId, onFailure)) {
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
			startVariations: { |project, providerId, modelId, prompt, maxCandidates, approveRenders, settings, context,
				onCandidate, onDone, onFailure|
				var session;
				if(sameModel.(providerId, modelId, onFailure)) {
					session = classes[\MBVariationSession].new(agentFor.(project, providerId), project,
						maxCandidates, settings, context);
					session.start(prompt, onCandidate, onDone, onFailure, approveRenders == true);
					session
				}
			},
			renderCandidate: { |session, index, onProgress, onSuccess, onFailure|
				session.renderCandidate(index, true, onProgress, onSuccess, onFailure)
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
			startVariations: fail, stopVariations: { nil }, applyVariation: fail, renderCandidate: fail,
			cancel: { nil }, play: fail, stopPlayback: { nil }, reveal: { nil }
		)
	}
}
