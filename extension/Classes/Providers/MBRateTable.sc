// Versioned provider/model token rates (extension/Data/provider-rates.json).
// Rates are USD per 1,000,000 tokens. A model, rate field, or tier that is
// not in the table is unknown (nil), never zero.
MBRateTable {
	var <path, <data, <loadError;

	*default { ^this.new(MBProviderPaths.dataDir +/+ "provider-rates.json") }

	*new { |path| ^super.new.prInit(path) }

	prInit { |argPath|
		path = argPath;
		data = try { MBJSON.parse(File.readAllString(path)) } { |error|
			loadError = MBError(\config, "Rate table could not be loaded: "
				++ MBRedact.string(error.errorString));
			nil
		};
	}

	isValid { ^data.isKindOf(Dictionary) and: { data["schema"] == 1 } }
	version { ^if(this.isValid) { data["version"] } }
	retrieved { ^if(this.isValid) { data["retrieved"] } }
	creditsPerUSD { ^if(this.isValid) { data["creditsPerUSD"] } }
	staleAfterDays { ^if(this.isValid) { data["staleAfterDays"] } }

	// "YYYY-MM-DD" -> days since 1970-01-01 (proleptic Gregorian).
	*dayNumber { |isoDate|
		var parts, y, m, d, era, yoe, doy, doe;
		if(isoDate.isString.not or: { isoDate.size < 10 }) { ^nil };
		parts = isoDate.keep(10).split($-).collect(_.asInteger);
		if(parts.size != 3) { ^nil };
		#y, m, d = parts;
		if(m <= 2) { y = y - 1 };
		era = (if(y >= 0) { y } { y - 399 } / 400).floor.asInteger;
		yoe = y - (era * 400);
		doy = ((153 * (m + if(m > 2) { -3 } { 9 })) + 2).div(5) + d - 1;
		doe = (yoe * 365) + yoe.div(4) - yoe.div(100) + doy;
		^(era * 146097) + doe - 719468
	}

	*today {
		var date = Date.getDate;
		^date.year.asString ++ "-" ++ date.month.asString.padLeft(2, "0") ++ "-"
			++ date.day.asString.padLeft(2, "0")
	}

	providerEntry { |provider|
		var providers = if(this.isValid) { data["providers"] };
		^if(providers.isKindOf(Dictionary)) { providers[provider.asString] }
	}

	// Exact id, a listed alias, or the id without a -YYYY-MM-DD / -YYYYMMDD
	// snapshot suffix. Returns [matchedId, rates] or nil.
	lookup { |provider, model|
		var models, entry = this.providerEntry(provider), base, candidates;
		if(entry.isNil or: { model.isNil }) { ^nil };
		models = entry["models"];
		if(models.isKindOf(Dictionary).not) { ^nil };
		model = model.asString;
		if(models[model].notNil) { ^[model, models[model]] };
		models.keysValuesDo { |key, rates|
			if((rates["aliases"] ? []).includes(model)) { ^[key, rates] }
		};
		candidates = [
			model.findRegexp("^(.*)-[0-9]{4}-[0-9]{2}-[0-9]{2}$"),
			model.findRegexp("^(.*)-[0-9]{8}$")
		];
		candidates.do { |match|
			if(match.size >= 2) {
				base = match[1][1];
				if(models[base].notNil) { ^[base, models[base]] };
			}
		};
		^nil
	}

	// Returns (usd: Float or nil, status: \ok/\missing/\stale, reason:, matchedModel:).
	estimate { |provider, model, usage, today|
		var found, rates, tier, input, cached, write, write1h, output, uncached, usd, status, day,
			staleDays, validUntil;
		if(this.isValid.not) { ^(usd: nil, status: \missing, reason: "rate table unavailable") };
		if(usage.isNil) { ^(usd: nil, status: \missing, reason: "provider reported no usage") };
		found = this.lookup(provider, model);
		if(found.isNil) { ^(usd: nil, status: \missing, reason: "no verified rate for this model") };
		rates = found[1];
		input = usage[\inputTokens] ? 0;
		cached = usage[\cachedInputTokens] ? 0;
		write = usage[\cacheWriteInputTokens] ? 0;
		write1h = (usage[\cacheWrite1hInputTokens] ? 0).min(write);
		output = usage[\outputTokens] ? 0;
		if(rates["maxInputTokens"].notNil and: { input > rates["maxInputTokens"] }) {
			^(usd: nil, status: \missing, matchedModel: found[0],
				reason: "no verified rate above " ++ rates["maxInputTokens"] ++ " input tokens")
		};
		tier = rates;
		if(rates["longContext"].notNil and: { input > rates["longContext"]["thresholdInputTokens"] }) {
			tier = rates["longContext"]
		};
		uncached = input - cached - write;
		if(uncached < 0) { ^(usd: nil, status: \missing, reason: "inconsistent usage counts") };
		if(tier["input"].isNil or: { tier["output"].isNil }
			or: { cached > 0 and: { tier["cachedInput"].isNil } }
			or: { (write - write1h) > 0 and: { tier["cacheWrite"].isNil } }
			or: { write1h > 0 and: { tier["cacheWrite1h"].isNil } }) {
			^(usd: nil, status: \missing, matchedModel: found[0],
				reason: "no verified rate for part of this usage")
		};
		#uncached, cached, write, write1h, output = [uncached, cached, write, write1h, output].collect(_.asFloat);
		usd = (uncached * tier["input"]) + (cached * (tier["cachedInput"] ? 0))
			+ ((write - write1h) * (tier["cacheWrite"] ? 0)) + (write1h * (tier["cacheWrite1h"] ? 0))
			+ (output * tier["output"]);
		usd = usd / 1e6;
		status = \ok;
		day = this.class.dayNumber(today ? this.class.today);
		staleDays = this.staleAfterDays;
		if(day.notNil and: { staleDays.notNil }
			and: { day - this.class.dayNumber(this.providerEntry(provider)["retrieved"] ? this.retrieved) > staleDays }) {
			status = \stale
		};
		validUntil = rates["validUntil"];
		if(day.notNil and: { validUntil.notNil } and: { day > this.class.dayNumber(validUntil) }) {
			status = \stale
		};
		^(usd: usd.asFloat, status: status, matchedModel: found[0],
			reason: if(status == \stale) { "rates may be out of date" } { nil })
	}
}
