// OpenAI Responses API (POST /v1/responses) and Models API (GET /v1/models).
// Requests use store: false so OpenAI does not retain the conversation state.
MBOpenAIProvider : MBProvider {
	classvar <unusableMarkers;

	*initClass {
		unusableMarkers = [
			["embedding", "Embedding model; cannot generate text"],
			["tts", "Text-to-speech model; cannot generate text"],
			["whisper", "Speech-to-text model; cannot generate text"],
			["transcribe", "Speech-to-text model; cannot generate text"],
			["audio", "Audio model; not supported by this assistant"],
			["realtime", "Realtime model; not supported by this assistant"],
			["dall-e", "Image model; cannot generate text"],
			["image", "Image model; cannot generate text"],
			["moderation", "Moderation model; cannot generate text"],
			["search", "Search-only model; not supported by this assistant"],
			["deep-research", "Requires research tools; not supported by this assistant"],
			["computer-use", "Requires computer-use tools; not supported by this assistant"],
			["instruct", "Legacy completions-only model"],
			["davinci", "Legacy completions-only model"],
			["babbage", "Legacy completions-only model"]
		];
	}

	*new { |store, baseUrl, timeout|
		^super.new.prInitProvider(\openai, "OpenAI", store, baseUrl, timeout)
	}

	defaultBaseUrl { ^"https://api.openai.com" }
	authHeader { ^"Authorization: Bearer " }
	headers { ^["Content-Type: application/json", "Accept: application/json"] }

	errorMessage { |json|
		var error = json["error"];
		^if(error.isKindOf(Dictionary)) { error["message"] } {
			if(error.isString) { error }
		}
	}

	isModelError { |status, json|
		var error = if(json.isKindOf(Dictionary)) { json["error"] };
		var code = if(error.isKindOf(Dictionary)) { error["code"] };
		^code == "model_not_found" or: { status == 404 and: { code.isNil or: { code == "not_found" } }
			and: { (this.errorMessage(json ? Dictionary.new) ? "").contains("model") } }
	}

	requestIdFrom { |headers, json|
		^(headers !? { headers["x-request-id"] }) ?? { json !? { json["id"] } }
	}

	classifyModel { |modelId|
		var lower = modelId.toLower, hit;
		hit = unusableMarkers.detect { |pair| lower.contains(pair[0]) };
		if(hit.notNil) { ^[false, hit[1]] };
		if(lower.beginsWith("gpt-") or: { lower.beginsWith("chatgpt-") }
			or: { lower.beginsWith("o1") } or: { lower.beginsWith("o3") }
			or: { lower.beginsWith("o4") } or: { lower.beginsWith("ft:gpt-") }) {
			^[true, "Text generation (Responses API)"]
		};
		^[false, "Not a recognized text-generation model"]
	}

	listModels { |onSuccess, onFailure|
		var handle = this.prNewHandle(onFailure);
		this.prSend(handle, "GET", "/v1/models", nil, { |json|
			var data = json["data"];
			if(data.isKindOf(SequenceableCollection).not) {
				MBError(\parse, "OpenAI model list has no data array").throw
			};
			data.select { |item| item.isKindOf(Dictionary) and: { item["id"].isString } }
			.collect { |item|
				var usable, note;
				#usable, note = this.classifyModel(item["id"]);
				(id: item["id"], displayName: item["id"], provider: id, usable: usable, note: note)
			}.sort { |a, b| a[\id] <= b[\id] }
		}, { |models, error|
			if(handle.finish) { if(error.notNil) { onFailure.value(error) } { onSuccess.value(models) } }
		});
		^handle
	}

	requestBody { |request|
		var body = Dictionary[
			"model" -> request[\model].asString,
			"input" -> request[\messages].collect { |message|
				Dictionary["role" -> message[\role].asString, "content" -> message[\content]]
			},
			"max_output_tokens" -> request[\maxOutputTokens],
			"store" -> false
		];
		if(request[\system].notNil and: { request[\system].notEmpty }) {
			body["instructions"] = request[\system]
		};
		if(request[\temperature].notNil) { body["temperature"] = request[\temperature].asFloat };
		^body
	}

	parseResponse { |json, headers, request|
		var texts = List.new, refusal, usage, details, status, incomplete, reason, text;
		status = json["status"];
		if(status == "failed") {
			MBError(\server, "OpenAI reported a failed response: "
				++ (this.errorMessage(json) ? "no detail")).throw
		};
		(json["output"] ? []).do { |item|
			if(item.isKindOf(Dictionary) and: { item["type"] == "message" }) {
				(item["content"] ? []).do { |part|
					if(part.isKindOf(Dictionary)) {
						if(part["type"] == "output_text" and: { part["text"].isString }) {
							texts.add(part["text"])
						};
						if(part["type"] == "refusal" and: { part["refusal"].isString }) {
							refusal = part["refusal"]
						};
					}
				}
			}
		};
		incomplete = json["incomplete_details"];
		reason = if(incomplete.isKindOf(Dictionary)) { incomplete["reason"] };
		text = texts.join;
		if(text.isEmpty and: { refusal.notNil }) { text = refusal; reason = "refusal" };
		if(text.isEmpty) {
			if(reason == "max_output_tokens") {
				MBError(\validation, "The model used all " ++ request[\maxOutputTokens]
					++ " output tokens before producing text; increase maxOutputTokens").throw
			};
			MBError(\parse, "OpenAI response contained no output text").throw
		};
		usage = json["usage"];
		if(usage.isKindOf(Dictionary)) {
			details = usage["input_tokens_details"] ?? { Dictionary.new };
			usage = (
				inputTokens: MBProvider.integerOr(usage["input_tokens"]),
				outputTokens: MBProvider.integerOr(usage["output_tokens"]),
				cachedInputTokens: MBProvider.integerOr(details["cached_tokens"]),
				cacheWriteInputTokens: MBProvider.integerOr(details["cache_write_tokens"])
			)
		} { usage = nil };
		^(provider: id, model: (json["model"] ? request[\model]).asString, text: text,
			usage: usage, requestId: this.requestIdFrom(headers, json),
			stopReason: reason ? status, responseId: json["id"])
	}

	complete { |request, onSuccess, onFailure|
		var handle = this.prNewHandle(onFailure), error = this.class.checkRequest(request);
		if(error.notNil) { ^this.prFailLater(handle, error, onFailure) };
		this.prSend(handle, "POST", "/v1/responses", this.requestBody(request),
			{ |json, headers| this.parseResponse(json, headers, request) },
			{ |response, failure|
				if(handle.finish) {
					if(failure.notNil) { onFailure.value(failure) } { onSuccess.value(response) }
				}
			});
		^handle
	}
}
