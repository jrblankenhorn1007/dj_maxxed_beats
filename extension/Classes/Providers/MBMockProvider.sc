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
	*digestValue { |string|
		var value = 5381;
		string.do { |char| value = ((value * 33) + (char.ascii & 255)) % 16777213 };
		^value
	}

	*digest { |string| ^this.digestValue(string).asHexString(6).toLower }

	// Text between `start` and the next `stop` in `text`, or nil.
	*between { |text, start, stop|
		var from = text.find(start), to;
		if(from.isNil) { ^nil };
		from = from + start.size;
		to = text.find(stop, offset: from) ? text.size;
		^text.copyRange(from, to - 1)
	}

	// A valid maxxedbeats.proposal/1 reply (docs/design/workflow.md) whose
	// edit is a renderable ChaosOsc composition. It depends only on the
	// request: the seed (the workflow's "Required seed", else derived from the
	// request digest) picks root, chaos amount, and the note pattern, so each
	// variation candidate differs. The entry being rendered, else the first
	// selected .scd file, is replaced; otherwise a new mock-<digest>.scd is created.
	*defaultResponder {
		^{ |request|
			var last = request[\messages].last[\content], text, number, digest, seed, seedText;
			var entry, target, action, roots, scales, scale, root, bpm, chaos, step, code, variation, describe;
			text = request[\model].asString ++ "\n" ++ (request[\system] ? "")
				++ "\n" ++ request[\messages].collect { |m| m[\role].asString ++ ":" ++ m[\content] }.join("\n");
			number = this.digestValue(text);
			digest = this.digest(text);
			seedText = this.between(last, "Use seed ", " ");
			seed = seedText !? { seedText.asFloat };
			if(seed.isNil or: { seed <= 0 } or: { seed >= 1 }) { seed = ((number % 9000) + 500) / 10000 };
			entry = this.between(last, "## Composition to render\n\n", "\n");
			target = if(entry.notNil and: { entry.toLower.endsWith(".scd") }) { entry } {
				this.between(last, "### File: ", "\n") !? { |file| if(file.toLower.endsWith(".scd")) { file } }
			};
			action = if(target.notNil) { "replace" } { "create" };
			target = target ?? { "mock-" ++ digest ++ ".scd" };
			roots = [98.0, 110.0, 130.81, 146.83, 164.81];
			scales = [["minor pentatonic", [0, 3, 5, 7, 10]], ["major pentatonic", [0, 2, 4, 7, 9]],
				["phrygian", [0, 1, 3, 7, 8]]];
			scale = scales[number % scales.size];
			root = roots[(seed * roots.size).floor.asInteger.clip(0, roots.size - 1)];
			bpm = 92 + ((number % 7) * 6);
			chaos = (3.55 + (seed * 0.4)).round(0.001);
			step = if(seed > 0.5) { 2 } { 1 };
			variation = this.between(last, "This is candidate ", " in a");
			describe = scale[0] ++ " ChaosOsc pattern on " ++ root ++ " Hz at " ++ bpm ++ " BPM, chaos "
				++ chaos ++ ", seed " ++ seed ++ (variation !? { |v| " (candidate " ++ v ++ ")" } ? "");
			code = [
				"// MaxxedBeats mock DJ sketch " ++ digest ++ ": deterministic and offline (no model was called).",
				"// " ++ describe,
				"(",
				"var settings = ~mbRender ? (duration: 8, seed: " ++ seed ++ ");",
				"var duration = settings[\\duration] ? 8;",
				"var seed = settings[\\seed] ? " ++ seed ++ ";",
				"var root = " ++ root ++ ", step = 60 / " ++ bpm ++ " / " ++ step ++ ", chaos = " ++ chaos ++ ";",
				"var degrees = " ++ scale[1].asCompileString ++ ";",
				"var def = SynthDef(\\mbMockVoice, { |out = 0, freq = 220, seed = 0.5, amp = 0.15, sustain = 0.25|",
				"\tvar env = EnvGen.kr(Env.perc(0.005, sustain), doneAction: 2);",
				"\tvar grit = LeakDC.ar(ChaosOsc.ar(chaos, seed, freq * 2));",
				"\tvar tone = SinOsc.ar(freq * (1 + (grit * 0.01)));",
				"\tOut.ar(out, Pan2.ar((tone * 0.75) + (grit * 0.2), (seed * 1.6) - 0.8) * env * amp);",
				"});",
				"var events = [[0.0, [\\d_recv, def.asBytes]]];",
				"var time = 0, index = 0;",
				"thisThread.randSeed = (seed * 1000000).asInteger;",
				"while { time < duration } {",
				"\tevents = events.add([time, [\\s_new, \\mbMockVoice, 2000 + index, 0, 0,",
				"\t\t\\freq, root * (2 ** ((degrees.choose + (12 * [0, 0, 1].choose)) / 12)),",
				"\t\t\\seed, (seed + (index * 0.0137)).wrap(0.01, 0.99),",
				"\t\t\\amp, 0.12 + 0.06.rand, \\sustain, step * 0.9]]);",
				"\ttime = time + step;",
				"\tindex = index + 1;",
				"};",
				"Score(events)",
				")",
				""
			].join("\n");
			MBJSON.encode((
				format: "maxxedbeats.proposal/1",
				plan: "Mock DJ sketch: " ++ describe ++ ". Short plucked notes; ChaosOsc adds grit and pitch drift.",
				summary: (if(action == "replace") { "Replaces " } { "Creates " }) ++ target
					++ " with a deterministic ChaosOsc sketch (mock " ++ digest ++ ").",
				assumptions: ["The mock DJ does not read the musical intent of the prompt; output depends only on the request and seed."],
				uncertainty: ["Offline mock response: not composed by a language model. Render and listen before keeping it."],
				questions: [],
				edits: [(path: target, action: action, newText: code)],
				entry: target,
				render: (duration: 8, sampleRate: 48000, numChannels: 2),
				seed: seed
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
			[MBOpenAIProvider.new(store), MBAnthropicProvider.new(store), MBMockProvider.new,
				MBCopilotProvider.new]
		};
	}

	at { |id| ^id !? { providers.detect { |p| p.id == id.asSymbol } } }

	ids { ^providers.collect(_.id) }
}
