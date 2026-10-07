// Anthropic Messages API (POST /v1/messages) and Models API
// (GET /v1/models, paginated with after_id).
MBAnthropicProvider : MBProvider {
	classvar <apiVersion = "2023-06-01", <>maxModelPages = 20;

	*new { |store, baseUrl, timeout|
		^super.new.prInitProvider(\anthropic, "Anthropic (Claude)", store, baseUrl, timeout)
	}

	defaultBaseUrl { ^"https://api.anthropic.com" }
	authHeader { ^"x-api-key: " }

	headers {
		^["Content-Type: application/json", "Accept: application/json",
			"anthropic-version: " ++ apiVersion]
	}

	errorMessage { |json|
		var error = json["error"];
		^if(error.isKindOf(Dictionary)) {
			[error["type"], error["message"]].select(_.isString).join(": ")
		}
	}

	isModelError { |status, json|
		var error = if(json.isKindOf(Dictionary)) { json["error"] };
		var type = if(error.isKindOf(Dictionary)) { error["type"] };
		var message = if(error.isKindOf(Dictionary)) { error["message"] } ? "";
		^status == 404 and: { type == "not_found_error" } and: { message.isString }
			and: { message.toLower.contains("model") }
	}

	requestIdFrom { |headers, json|
		^(headers !? { headers["request-id"] }) ?? { json !? { json["id"] } }
	}

	listModels { |onSuccess, onFailure|
		var handle = this.prNewHandle(onFailure), models = List.new, fetch;
		fetch = { |afterId, page|
			var path = "/v1/models?limit=1000";
			if(afterId.notNil) { path = path ++ "&after_id=" ++ afterId };
			this.prSend(handle, "GET", path, nil, { |json|
				var data = json["data"];
				if(data.isKindOf(SequenceableCollection).not) {
					MBError(\parse, "Anthropic model list has no data array").throw
				};
				data.do { |item|
					if(item.isKindOf(Dictionary) and: { item["id"].isString }) {
						models.add((id: item["id"], displayName: item["display_name"] ? item["id"],
							provider: id, usable: true, note: "Text generation (Messages API)"))
					}
				};
				[json["has_more"] == true, json["last_id"]]
			}, { |more, error|
				case
				{ error.notNil } { if(handle.finish) { onFailure.value(error) } }
				{ more[0] and: { more[1].isString } and: { page < maxModelPages } } {
					fetch.value(more[1], page + 1)
				}
				{ if(handle.finish) { onSuccess.value(models.asArray) } };
			});
		};
		fetch.value(nil, 1);
		^handle
	}

	requestBody { |request|
		var body = Dictionary[
			"model" -> request[\model].asString,
			"max_tokens" -> request[\maxOutputTokens],
			"messages" -> request[\messages].collect { |message|
				Dictionary["role" -> message[\role].asString, "content" -> message[\content]]
			}
		];
		if(request[\system].notNil and: { request[\system].notEmpty }) {
			body["system"] = request[\system]
		};
		if(request[\temperature].notNil) {
			body["temperature"] = request[\temperature].asFloat
		};
		^body
	}

	parseResponse { |json, headers, request|
		var texts = List.new, usage, read, write, write1h, creation, reason, text;
		if(json["type"] == "error") {
			MBError(\server, "Anthropic error: " ++ (this.errorMessage(json) ? "no detail")).throw
		};
		(json["content"] ? []).do { |block|
			if(block.isKindOf(Dictionary) and: { block["type"] == "text" }
				and: { block["text"].isString }) {
				texts.add(block["text"])
			}
		};
		reason = json["stop_reason"];
		text = texts.join;
		if(text.isEmpty and: { reason != "refusal" }) {
			if(reason == "max_tokens") {
				MBError(\validation, "The model used all " ++ request[\maxOutputTokens]
					++ " output tokens before producing text; increase maxOutputTokens").throw
			};
			MBError(\parse, "Anthropic response contained no text").throw
		};
		usage = json["usage"];
		if(usage.isKindOf(Dictionary)) {
			read = MBProvider.integerOr(usage["cache_read_input_tokens"]);
			write = MBProvider.integerOr(usage["cache_creation_input_tokens"]);
			creation = usage["cache_creation"];
			write1h = if(creation.isKindOf(Dictionary)) {
				MBProvider.integerOr(creation["ephemeral_1h_input_tokens"])
			} { 0 };
			usage = (
				inputTokens: MBProvider.integerOr(usage["input_tokens"]) + read + write,
				outputTokens: MBProvider.integerOr(usage["output_tokens"]),
				cachedInputTokens: read,
				cacheWriteInputTokens: write
			);
			if(write1h > 0) { usage[\cacheWrite1hInputTokens] = write1h };
		} { usage = nil };
		^(provider: id, model: (json["model"] ? request[\model]).asString, text: text,
			usage: usage, requestId: this.requestIdFrom(headers, json),
			stopReason: reason, responseId: json["id"])
	}

	complete { |request, onSuccess, onFailure|
		var handle = this.prNewHandle(onFailure), error = this.class.checkRequest(request);
		if(error.isNil and: { request[\temperature].notNil } and: { request[\temperature] > 1 }) {
			error = MBError(\validation, "Anthropic temperature must be from 0 to 1")
		};
		if(error.notNil) { ^this.prFailLater(handle, error, onFailure) };
		this.prSend(handle, "POST", "/v1/messages", this.requestBody(request),
			{ |json, headers| this.parseResponse(json, headers, request) },
			{ |response, failure|
				if(handle.finish) {
					if(failure.notNil) { onFailure.value(failure) } { onSuccess.value(response) }
				}
			});
		^handle
	}
}
