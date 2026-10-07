// Deterministic offline provider for tests, demos, and the visual test plan.
// Never touches the network and costs nothing. Output depends only on the
// request, so identical requests produce identical text.
//
// Adjusting behaviour:
//   mock.responder = { |request| "text" };  // default: MBMockProvider.defaultResponder
//   mock.enqueue("text" or MBError(...) or { |request| "text" });  // one-shot, FIFO
//   mock.latency = 0.2;  mock.models = [...];  mock.listModelsError = MBError(\network, "...");
MBMockProvider : MBProvider {
	var <>responder, <>latency = 0, <>models, <>listModelsError, queue, counter = 0;

	*new { |responder|
		^super.new.prInitProvider(\mock, "Mock DJ (offline)", MBCredentialStore.fake,
			"http://127.0.0.1/mock", nil).prInitMock(responder)
	}

	prInitMock { |argResponder|
		responder = argResponder ? this.class.defaultResponder;
		queue = List.new;
		models = this.class.defaultModels;
	}

	*defaultModels {
		^[
			(id: "mock-composer-1", displayName: "Mock Composer", provider: \mock, usable: true,
				note: "Deterministic offline responses; no network and no cost"),
			(id: "mock-legacy-0", displayName: "Mock Legacy", provider: \mock, usable: false,
				note: "Listed but unusable, to exercise model filtering")
		]
	}

	// Stable across runs and platforms (unlike String.hash).
	*digest { |string|
		var value = 5381;
		string.do { |char| value = ((value * 33) + (char.ascii & 255)) % 16777213 };
		^value.asHexString(6).toLower
	}

	// Placeholder format until the workflow layer defines the composition
	// response format; JSON so it can be parsed and asserted on.
	*defaultResponder {
		^{ |request|
			var last = request[\messages].last[\content], digest;
			digest = this.digest(request[\model].asString ++ "\n" ++ (request[\system] ? "")
				++ "\n" ++ request[\messages].collect { |m| m[\role].asString ++ ":" ++ m[\content] }.join("\n"));
			MBJSON.encode((
				mock: true,
				digest: digest,
				plan: "Mock plan " ++ digest ++ " for: " ++ last.keep(80),
				summary: "Deterministic mock response (no provider was called)",
				edits: []
			))
		}
	}

	enqueue { |item| queue.add(item) }

	listModels { |onSuccess, onFailure|
		var handle = this.prNewHandle(onFailure);
		this.prLater(handle, {
			if(listModelsError.notNil) { onFailure.value(listModelsError) } {
				onSuccess.value(models.collect(_.copy))
			}
		});
		^handle
	}

	complete { |request, onSuccess, onFailure|
		var handle = this.prNewHandle(onFailure), error = this.class.checkRequest(request), item;
		if(error.isNil and: {
			models.detect { |m| m[\id] == request[\model].asString and: { m[\usable] } }.isNil
		}) {
			error = MBError(\unavailableModel, "Mock model is not available: " ++ request[\model])
		};
		if(error.notNil) { ^this.prFailLater(handle, error, onFailure) };
		item = if(queue.notEmpty) { queue.removeAt(0) } { responder };
		this.prLater(handle, {
			var text = if(item.isKindOf(MBError)) { item } { item.value(request) };
			var input;
			if(text.isKindOf(MBError)) { onFailure.value(text) } {
				counter = counter + 1;
				input = (request[\system] ? "").size + request[\messages].sum { |m| m[\content].size };
				onSuccess.value((provider: \mock, model: request[\model].asString, text: text.asString,
					usage: (inputTokens: (input / 4).ceil.asInteger,
						outputTokens: (text.asString.size / 4).ceil.asInteger,
						cachedInputTokens: 0, cacheWriteInputTokens: 0),
					requestId: "mock-" ++ counter, stopReason: "end_turn",
					responseId: "mock-" ++ counter))
			}
		});
		^handle
	}

	prLater { |handle, action|
		AppClock.sched(latency.max(0), { if(handle.finish) { action.value }; nil });
	}
}

// Registry of the available providers: \openai, \anthropic, \mock.
MBProviderRegistry {
	classvar default;
	var <store, <providers;

	*default { ^default ?? { default = this.new } }

	*new { |store, providers|
		^super.new.prInit(store ?? { MBCredentialStore.default }, providers)
	}

	prInit { |argStore, argProviders|
		store = argStore;
		providers = argProviders ?? {
			[MBOpenAIProvider.new(store), MBAnthropicProvider.new(store), MBMockProvider.new]
		};
	}

	at { |id| ^id !? { providers.detect { |p| p.id == id.asSymbol } } }

	ids { ^providers.collect(_.id) }
}
