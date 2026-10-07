// Pure text formatting for the MaxxedBeats agent window. No state, no I/O.
// Data records follow docs/design/CONTRACT.md and are read with `at`, so
// Events and dictionaries both work.

MBGuiFormat {
	classvar <creditsPerUSD = 100;

	*redact { |text, secrets|
		var out = text.asString;
		secrets.do { |secret|
			secret = secret.asString;
			if(secret.size >= 4) {
				while { out.find(secret).notNil } { out = out.replace(secret, "[redacted]") };
			};
		};
		out = out.replaceRegexp("sk-[A-Za-z0-9_\\-]{6,}", "[redacted]");
		out = out.replaceRegexp("(Bearer)\\s+[^\\s\"',;]+", "$1 [redacted]");
		out = out.replaceRegexp("([Xx]-[Aa][Pp][Ii]-[Kk][Ee][Yy][\"']?\\s*[:=]\\s*[\"']?)[^\\s\"',;]+", "$1[redacted]");
		^out
	}

	*asError { |error, secrets|
		var kind, detail;
		case
		{ error.isKindOf(MBError) } { kind = error.kind; detail = error.detail }
		{ error.isKindOf(Exception) } { kind = \config; detail = error.errorString }
		{ error.isNil } { kind = \config; detail = "unknown failure" }
		{ kind = \config; detail = error.asString };
		^MBError(kind, this.redact(detail, secrets))
	}

	*errorText { |error|
		var e = this.asError(error);
		^"Error (" ++ e.kind ++ "): " ++ e.detail
	}

	*fixed { |number, decimals = 2|
		var scale = (10 ** decimals).asInteger;
		var scaled = (number.abs * scale).round.asInteger;
		var frac = (scaled % scale).asString;
		while { frac.size < decimals } { frac = "0" ++ frac };
		^(if(number < 0 and: { scaled > 0 }) { "-" } { "" })
			++ (scaled div: scale).asString
			++ (if(decimals > 0) { "." ++ frac } { "" })
	}

	*count { |n| ^if(n.isNumber) { n.asInteger.asString } { "?" } }

	*usd { |usd| ^if(usd.isNumber) { "US$" ++ this.fixed(usd, 4) } }

	*credits { |credits| ^if(credits.isNumber) { this.fixed(credits, 2) } }

	*rateText { |record|
		var table = record[\rateTable];
		var tableText = if(table.notNil and: { table.asString.size > 0 }) {
			"rate table " ++ table
		} { "no rate table" };
		^switch((record[\rateStatus] ? \missing).asSymbol,
			\ok, { tableText },
			\stale, { "STALE rates (" ++ tableText ++ ")" },
			{ "rates MISSING (" ++ tableText ++ ")" }
		)
	}

	*costText { |record|
		var usd = this.usd(record[\usd]);
		var credits = this.credits(record[\credits]);
		var stale = (record[\rateStatus] ? \missing).asSymbol == \stale;
		var usdText = case
		{ record[\usd] == 0 } { "no cost (US$0, free/offline model)" }
		{ usd.notNil } { "est. " ++ usd ++ (if(stale) { " (stale)" } { "" }) }
		{ "est. USD unavailable" };
		var creditText = if(credits.notNil) { credits ++ " credits (estimate)" } { "credits unavailable" };
		^usdText ++ " · " ++ creditText ++ " · " ++ this.rateText(record)
	}

	*tokenText { |record|
		^"in " ++ this.count(record[\inputTokens])
			++ " · out " ++ this.count(record[\outputTokens])
			++ " · cached " ++ this.count(record[\cachedInputTokens]) ++ " tokens"
	}

	*usageLine { |record|
		var who;
		if(record.isNil) { ^"Usage not reported for the last request (or no request yet)." };
		who = (record[\provider] ? "?").asString ++ " / " ++ (record[\model] ? "?").asString;
		^who ++ " — " ++ this.tokenText(record) ++ " — " ++ this.costText(record)
	}

	*totalsLine { |totals|
		var requests;
		if(totals.isNil) { ^"No usage recorded in this session." };
		requests = totals[\requests];
		^(if(requests.notNil) { requests.asString ++ " request(s) — " } { "" })
			++ this.tokenText(totals) ++ " — " ++ this.costText(totals)
			++ (if((totals[\unpricedRequests] ? 0) > 0) {
				" · " ++ totals[\unpricedRequests] ++ " request(s) unpriced (not included in USD)"
			} { "" })
	}

	*creditNote {
		^"Credits are an informational estimate (" ++ creditsPerUSD
			++ " credits per estimated US$1), not a balance, invoice, or exact bill. "
			++ "Your provider bills your own API account. Missing or stale rates are "
			++ "labelled and never shown as zero."
	}

	*privacyNotice {
		^"Privacy: your prompt, the conversation, and only the project files you select "
			++ "are sent to the provider you choose (OpenAI or Anthropic). Nothing else is "
			++ "sent anywhere, and usage history stays on this computer.\n\n"
			++ "API cost: requests may incur charges on your provider account. "
			++ this.creditNote ++ "\n\n"
			++ "Keys: API keys are kept in your operating system's credential store "
			++ "(macOS Keychain, Windows Credential Manager, Linux Secret Service). They are "
			++ "never displayed, logged, or written to settings or project files. Typed or "
			++ "pasted keys are masked; editing inside a key is not supported, so use Clear "
			++ "and paste again."
	}

	*providerLabel { |info|
		^(info[\displayName] ? info[\id]).asString ++ " (" ++ info[\id].asString ++ ")"
	}

	*modelLabel { |model|
		var id = model[\id].asString;
		var name = model[\displayName];
		var note = model[\note];
		var text = id ++ (if(name.notNil and: { name.asString != id }) { " — " ++ name } { "" });
		if(model[\usable] != true) {
			text = text ++ " [unavailable"
				++ (if(note.notNil and: { note.asString.size > 0 }) { ": " ++ note } { "" }) ++ "]";
		};
		^text
	}

	*checkWarnings { |checks|
		var warnings = List.new;
		if(checks.isNil) { ^["render checks were not reported"] };
		if(checks[\finite] == false) { warnings.add("audio contains NaN/inf samples") };
		if(checks[\silent] == true) { warnings.add("audio is silent") };
		if(checks[\clipped] == true) { warnings.add("audio clips") };
		if(checks[\durationOk] == false) { warnings.add("duration does not match the settings") };
		^warnings.asArray
	}

	*checksText { |checks|
		var warnings = this.checkWarnings(checks);
		^if(warnings.isEmpty) {
			"checks OK (finite, not silent, no clipping, duration)"
		} { "WARNING: " ++ warnings.join("; ") }
	}

	*renderText { |result, root|
		var duration;
		if(result.isNil) { ^"No render yet." };
		duration = result[\duration];
		^[
			"File: " ++ this.displayPath(result[\path], root),
			"Duration " ++ (if(duration.isNumber) { this.fixed(duration, 2) ++ " s" } { "?" })
				++ " · " ++ (result[\sampleRate] ? "?") ++ " Hz · "
				++ (result[\numChannels] ? "?") ++ " ch"
				++ (result[\metadataPath] !? { |m| " · metadata " ++ m.basename } ? ""),
			this.checksText(result[\checks])
		].join("\n")
	}

	*candidateAudioPath { |candidate|
		var render = candidate[\render];
		^candidate[\renderPath] ?? { if(render.notNil) { render[\path] } { candidate[\audioPath] } }
	}

	*candidateLine { |candidate, index|
		var render = candidate[\render];
		var checks = candidate[\checks] ?? { if(render.notNil) { render[\checks] } };
		var parts = ["#" ++ (index + 1)];
		if(candidate[\seed].notNil) { parts = parts.add("seed " ++ candidate[\seed]) };
		parts = parts.add(case
			{ candidate[\status] == \failed } {
				"FAILED" ++ (candidate[\error] !? { |e| " (" ++ this.asError(e).kind ++ "): " ++ this.asError(e).detail } ? "")
			}
			{ candidate[\status] == \rendering } { "rendering..." }
			{ this.candidateAudioPath(candidate).isNil } { "not rendered" }
			{ this.checksText(checks) });
		parts = parts.add((candidate[\plan] ? candidate[\summary] ? "").asString.keep(160));
		^parts.join(" — ")
	}

	*fileCount { |n| ^n.asString ++ (if(n == 1) { " file" } { " files" }) }

	// A path inside `root` is shown relative to it; others are shown whole.
	*displayPath { |path, root|
		path = path.asString;
		if(root.notNil and: { path.beginsWith(root.asString +/+ "") }) { ^path.copyToEnd(root.asString.size + 1) };
		^path
	}

	*timeText { |time|
		if(time.isNil) { ^"unknown" };
		^if(time.isNumber) { Date(rawSeconds: time).format("%Y-%m-%d %H:%M") } { time.asString }
	}

	*planText { |proposal|
		var text = (proposal[\plan] ? "(no plan)").asString;
		[[\assumptions, "Assumptions"], [\uncertainty, "Uncertainty"], [\questions, "Questions for you"]].do { |pair|
			var items = proposal[pair[0]];
			if(items.notNil and: { items.notEmpty }) {
				text = text ++ "\n\n" ++ pair[1] ++ ":\n" ++ items.collect { |item| "- " ++ item }.join("\n")
			};
		};
		^text
	}

	*diffText { |edits|
		if(edits.isNil or: { edits.isEmpty }) { ^"No file changes proposed." };
		^edits.collect { |edit|
			"=== " ++ edit.path ++ (if(edit.isNew == true) { " (new file)" } { "" }) ++ " ===\n"
				++ edit.diffString
		}.join("\n")
	}
}
