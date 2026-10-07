// Base class for model providers. Subclasses map the contract request
//   (model:, system:, messages: [(role:, content:)], maxOutputTokens:, temperature:)
// to their HTTP API and back to the contract response
//   (provider:, model:, text:, usage: (inputTokens:, outputTokens:,
//    cachedInputTokens:, cacheWriteInputTokens:) or nil, requestId:,
//    stopReason:, responseId:).
// inputTokens is the total input (including cache reads and writes).
// There are no silent retries and no provider or model fallback.
MBProvider {
	var <id, <displayName, <store, <baseUrl, <>timeout = 120, <>connectTimeout = 15;

	*checkRequest { |request|
		var messages, max, temperature;
		if(request.isKindOf(Dictionary).not) { ^MBError(\validation, "Request must be an Event") };
		if(request[\model].isNil or: { request[\model].asString.isEmpty }) {
			^MBError(\validation, "Request has no model; choose a model first")
		};
		messages = request[\messages];
		if(messages.isKindOf(SequenceableCollection).not or: { messages.isString }
			or: { messages.isEmpty }) {
			^MBError(\validation, "Request needs at least one message")
		};
		messages.do { |message, index|
			if(message.isKindOf(Dictionary).not
				or: { #[\user, \assistant].includes(message[\role].asSymbol).not }) {
				^MBError(\validation, "Message " ++ index ++ " role must be \\user or \\assistant")
			};
			if(message[\content].isString.not) {
				^MBError(\validation, "Message " ++ index ++ " content must be a String")
			};
		};
		if(request[\system].notNil and: { request[\system].isString.not }) {
			^MBError(\validation, "System prompt must be a String or nil")
		};
		max = request[\maxOutputTokens];
		if(max.isKindOf(Integer).not or: { max < 1 }) {
			^MBError(\validation, "maxOutputTokens must be a positive Integer")
		};
		temperature = request[\temperature];
		if(temperature.notNil and: { temperature.isNumber.not or: { temperature < 0 }
			or: { temperature > 2 } }) {
			^MBError(\validation, "temperature must be nil or a number from 0 to 2")
		};
		^nil
	}

	listModels { |onSuccess, onFailure| ^this.subclassResponsibility(thisMethod) }
	complete { |request, onSuccess, onFailure| ^this.subclassResponsibility(thisMethod) }

	// Hooks for HTTP providers.
	authHeader { ^nil }
	headers { ^[] }
	errorMessage { |json| ^nil }
	isModelError { |status, json| ^false }

	prAuth { ^(store: store, id: id, header: this.authHeader) }

	prFailLater { |handle, error, onFailure|
		{ if(handle.finish) { onFailure.value(error) } }.defer;
		^handle
	}

	prNewHandle { |onFailure|
		^MBRequestHandle({ { onFailure.value(MBError(\cancelled, "Request cancelled")) }.defer })
	}

	// Sends one HTTP request; parser.(json, headers) returns the result or
	// throws MBError. onResult.(value, error) runs unless cancelled.
	prSend { |handle, method, path, body, parser, onResult|
		handle.inner = MBHttp.request((
			method: method, url: baseUrl ++ path, headers: this.headers,
			body: body !? { MBJSON.encode(body) }, timeout: timeout,
			connectTimeout: connectTimeout, auth: this.prAuth
		), { |result|
			var value, error;
			if(handle.isDone.not) {
				#value, error = this.prInterpret(result, parser);
				onResult.value(value, error);
			}
		});
	}

	prInterpret { |result, parser|
		var json, value, error;
		if(result[\error].notNil) { ^[nil, result[\error]] };
		if(result[\status] >= 200 and: { result[\status] < 300 }) {
			error = try {
				json = MBJSON.parse(result[\body]);
				if(json.isKindOf(Dictionary).not) {
					MBError(\parse, displayName ++ " returned an unexpected JSON shape").throw
				};
				value = parser.value(json, result[\headers]);
				nil
			} { |caught|
				if(caught.isKindOf(MBError)) { caught } {
					MBError(\parse, displayName ++ " response could not be read: "
						++ MBRedact.string(caught.errorString))
				}
			};
			if(error.notNil and: { error.kind == \parse }) {
				error = MBError(\parse, MBRedact.string(error.detail
					++ " (HTTP " ++ result[\status] ++ this.prRequestIdNote(result[\headers]) ++ ")"))
			};
			^[value, error]
		};
		^[nil, this.httpError(result[\status], result[\headers], result[\body])]
	}

	prRequestIdNote { |headers|
		var requestId = this.requestIdFrom(headers, nil);
		^if(requestId.notNil) { ", request " ++ requestId } { "" }
	}

	requestIdFrom { |headers, json| ^nil }

	httpError { |status, headers, body|
		var json, message, kind, detail, retry;
		json = try { MBJSON.parse(body) } { nil };
		message = if(json.isKindOf(Dictionary)) { this.errorMessage(json) };
		kind = case
		{ this.isModelError(status, json) } { \unavailableModel }
		{ status == 401 or: { status == 403 } } { \auth }
		{ status == 429 } { \rateLimit }
		{ #[400, 409, 413, 422].includes(status) } { \validation }
		{ \server };
		detail = displayName ++ " HTTP " ++ status;
		if(message.notNil) { detail = detail ++ ": " ++ message };
		retry = headers !? { headers["retry-after"] };
		if(kind == \rateLimit and: { retry.notNil }) {
			detail = detail ++ " (retry after " ++ retry ++ " s)"
		};
		detail = detail ++ this.prRequestIdNote(headers);
		^MBError(kind, MBRedact.string(detail))
	}

	prInitProvider { |argId, argName, argStore, argBaseUrl, argTimeout|
		id = argId;
		displayName = argName;
		store = argStore ?? { MBCredentialStore.default };
		baseUrl = (argBaseUrl ? this.defaultBaseUrl).asString;
		while { baseUrl.endsWith("/") } { baseUrl = baseUrl.drop(-1) };
		timeout = argTimeout ? timeout;
	}

	defaultBaseUrl { ^nil }

	// Total characters of a parsed text list, joined in order.
	*joinTexts { |texts| ^texts.join }

	*integerOr { |value, default = 0|
		^if(value.isNumber) { value.asInteger } { default }
	}

	printOn { |stream| stream << this.class.name << "(" << id << ")" }
}
