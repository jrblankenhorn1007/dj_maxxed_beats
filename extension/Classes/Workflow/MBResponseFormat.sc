/*
The structured response contract between the model and the workflow.

A response must be exactly one JSON object (optionally wrapped in a single
```json fence) in the "maxxedbeats.proposal/1" format documented in
docs/design/workflow.md and agent/WORKFLOW.md. Anything else becomes
MBError(\parse) (not JSON) or MBError(\validation) (wrong shape, oversized,
out-of-project path, credential-like content). Parsing never touches files.
*/
MBResponseFormat {
	classvar <formatId = "maxxedbeats.proposal/1";
	classvar <>maxResponseBytes = 524288, <>maxEdits = 16, <>maxTotalEditBytes = 1048576;
	classvar <>maxPlanBytes = 16384, <>maxSummaryBytes = 4096, <>maxListItems = 32, <>maxListItemBytes = 2048;
	classvar <>minDuration = 1.0, <>maxDuration = 600.0, <>maxChannels = 8;
	classvar <topLevelKeys = #["format", "plan", "summary", "assumptions", "questions", "uncertainty", "edits", "entry", "render", "seed"];
	classvar <editKeys = #["path", "action", "oldText", "newText"];
	classvar <renderKeys = #["duration", "sampleRate", "numChannels"];
	classvar <sampleRates = #[22050, 32000, 44100, 48000, 88200, 96000, 192000];

	*fail { |kind, detail| MBError(kind, detail).throw }

	*containsSecret { |text|
		^text.isString and: {
			text.findRegexp("sk-[A-Za-z0-9_-]{16,}").notEmpty
			or: { text.findRegexp("-----BEGIN [A-Z ]*PRIVATE KEY-----").notEmpty }
		}
	}

	*redact { |text|
		var result = text.asString;
		result.findRegexp("sk-[A-Za-z0-9_-]{16,}").do { |match|
			result = result.replace(match[1], "[redacted]")
		};
		^result
	}

	*extract { |text|
		var trimmed = text.stripWhiteSpace, newline, language;
		if(trimmed.isEmpty) { this.fail(\parse, "the model returned an empty response") };
		if(trimmed.beginsWith("```")) {
			newline = trimmed.find("\n");
			if(newline.isNil or: { trimmed.size < 7 } or: { trimmed.endsWith("```").not }) {
				this.fail(\parse, "the response has an unterminated code fence")
			};
			language = trimmed.copyRange(3, newline - 1).stripWhiteSpace.toLower;
			if(language.notEmpty and: { language != "json" }) {
				this.fail(\parse, "the response must be a JSON object, not a " ++ language.keep(20) ++ " block")
			};
			^trimmed.copyRange(newline + 1, trimmed.size - 4)
		};
		^trimmed
	}

	*field { |dict, name|
		^dict[name] ?? { dict[name.asSymbol] }
	}

	*checkKeys { |dict, allowed, what|
		dict.keys.do { |key|
			if(allowed.includesEqual(key.asString).not) {
				this.fail(\validation, what ++ " has an unexpected field \"" ++ key.asString.keep(40) ++ "\"")
			}
		}
	}

	*requireString { |dict, name, maxBytes, nonEmpty = true|
		var value = this.field(dict, name);
		if(value.isString.not) { this.fail(\validation, "\"" ++ name ++ "\" must be a string") };
		if(nonEmpty and: { value.stripWhiteSpace.isEmpty }) { this.fail(\validation, "\"" ++ name ++ "\" must not be empty") };
		if(value.size > maxBytes) { this.fail(\validation, "\"" ++ name ++ "\" is longer than " ++ maxBytes ++ " bytes") };
		^value
	}

	*stringList { |dict, name|
		var value = this.field(dict, name);
		if(value.isNil) { ^[] };
		if(value.isKindOf(Array).not or: { value.size > maxListItems }
			or: { value.any { |item| item.isString.not or: { item.size > maxListItemBytes } } }) {
			this.fail(\validation, "\"" ++ name ++ "\" must be a list of at most " ++ maxListItems ++ " short strings")
		};
		^value
	}

	*integerValue { |value|
		^if(value.isKindOf(Integer)) { value } {
			if(value.isKindOf(Float) and: { value.abs < 1e9 } and: { value == value.round }) { value.asInteger } { nil }
		}
	}

	// Validates render settings from a response or from MBRenderer callers.
	*renderSettings { |dict, strictKeys = true|
		var duration, sampleRate, numChannels;
		if(dict.isKindOf(Dictionary).not) { this.fail(\validation, "render settings must be an object") };
		if(strictKeys) { this.checkKeys(dict, renderKeys, "render") };
		duration = this.field(dict, "duration");
		sampleRate = this.integerValue(this.field(dict, "sampleRate") ? 48000);
		numChannels = this.integerValue(this.field(dict, "numChannels") ? 2);
		if(duration.isKindOf(SimpleNumber).not or: { duration.isNaN }
			or: { duration < minDuration } or: { duration > maxDuration }) {
			this.fail(\validation, "render duration must be between " ++ minDuration ++ " and " ++ maxDuration ++ " seconds")
		};
		if(sampleRate.isNil or: { sampleRates.includes(sampleRate).not }) {
			this.fail(\validation, "render sampleRate must be one of " ++ sampleRates.join(", "))
		};
		if(numChannels.isNil or: { numChannels < 1 } or: { numChannels > maxChannels }) {
			this.fail(\validation, "render numChannels must be between 1 and " ++ maxChannels)
		};
		^(duration: duration.asFloat, sampleRate: sampleRate, numChannels: numChannels)
	}

	*seedValue { |value|
		if(value.isKindOf(SimpleNumber).not or: { value.isNaN } or: { value <= 0 } or: { value >= 1 }) {
			this.fail(\validation, "seed must be a number strictly between 0 and 1")
		};
		^value.asFloat
	}

	*parse { |text, project|
		var document, specs, paths, edits, entry, render, seed, totalBytes = 0;
		if(text.isString.not) { this.fail(\parse, "the provider returned no response text") };
		if(text.size > maxResponseBytes) {
			this.fail(\validation, "the response is larger than " ++ maxResponseBytes ++ " bytes and was discarded")
		};
		if(this.containsSecret(text)) {
			this.fail(\validation, "the response contains what looks like an API key or private key and was discarded; "
				++ "credentials must never be written into compositions")
		};
		document = MBWorkflowTry.value({ MBWorkflowJSON.parse(this.extract(text)) });
		if(document.isKindOf(Error)) {
			this.fail(\parse, "the response is not a JSON object in the " ++ formatId ++ " format ("
				++ (document.tryPerform(\detail) ? document.errorString) ++ ")")
		};
		if(document.isKindOf(Dictionary).not) {
			this.fail(\validation, "the response must be a JSON object in the " ++ formatId ++ " format")
		};
		this.checkKeys(document, topLevelKeys, "the response");
		if(document["format"] != formatId) {
			this.fail(\validation, "the response \"format\" must be \"" ++ formatId ++ "\"")
		};
		specs = document["edits"];
		if(specs.isKindOf(Array).not) { this.fail(\validation, "\"edits\" must be a list (use [] for no file changes)") };
		if(specs.size > maxEdits) { this.fail(\validation, "the response proposes more than " ++ maxEdits ++ " file edits") };
		specs.do { |spec, index|
			var what = "edit " ++ (index + 1);
			if(spec.isKindOf(Dictionary).not) { this.fail(\validation, what ++ " must be an object") };
			this.checkKeys(spec, editKeys, what);
			this.requireString(spec, "path", 240);
			this.requireString(spec, "action", 16);
			this.requireString(spec, "newText", MBProject.maxFileBytes, false);
			if(spec["oldText"].notNil and: { spec["oldText"].isString.not }) {
				this.fail(\validation, what ++ " \"oldText\" must be a string")
			};
			totalBytes = totalBytes + spec["newText"].size;
		};
		if(totalBytes > maxTotalEditBytes) { this.fail(\validation, "the proposed edits are too large in total") };
		paths = specs.collect { |spec| spec["path"] };
		if(paths.collect(_.toLower).asSet.size != paths.size) {
			this.fail(\validation, "the response edits the same file more than once; combine those changes")
		};
		edits = specs.collect { |spec| project.prepareEdit(spec) };
		entry = document["entry"];
		if(entry.notNil) {
			if(entry.isString.not or: { entry.toLower.endsWith(".scd").not }) {
				this.fail(\validation, "\"entry\" must name an .scd composition")
			};
			if(paths.includesEqual(entry).not and: { project.exists(entry).not }) {
				this.fail(\validation, "\"entry\" names a composition that does not exist in the project")
			};
		};
		render = document["render"] !? { |value| this.renderSettings(value) };
		seed = document["seed"] !? { |value| this.seedValue(value) };
		^(
			plan: this.requireString(document, "plan", maxPlanBytes),
			summary: this.requireString(document, "summary", maxSummaryBytes),
			assumptions: this.stringList(document, "assumptions"),
			questions: this.stringList(document, "questions"),
			uncertainty: this.stringList(document, "uncertainty"),
			edits: edits,
			entry: entry,
			render: render,
			seed: seed
		)
	}
}
