// Usage and estimated cost per model response, per-session totals, and a
// local history (settings dir, usage-history.json) the user can inspect and
// clear. Costs are estimates from MBRateTable; app credits are an internal,
// non-purchasable display unit (100 credits per estimated USD). Unknown cost
// is nil, never 0. Nothing here leaves the machine.
MBUsageMeter {
	classvar default, <>maxHistory = 5000;
	var <rateTable, <historyPath, <>today, session, history;

	*default { ^default ?? { default = this.new } }

	*new { |rateTable, historyPath, today|
		^super.new.prInit(rateTable, historyPath, today)
	}

	prInit { |argTable, argPath, argToday|
		rateTable = argTable ?? { MBRateTable.default };
		historyPath = argPath ?? { MBProviderPaths.settingsDir +/+ "usage-history.json" };
		today = argToday;
		session = List.new;
		history = List.new;
		this.prLoad;
	}

	creditsPerUSD { ^rateTable.creditsPerUSD ? 100 }

	record { |response|
		var usage = response[\usage], estimate, record;
		estimate = rateTable.estimate(response[\provider], response[\model], usage, today);
		record = (
			provider: response[\provider].asSymbol,
			model: response[\model].asString,
			inputTokens: usage !? { usage[\inputTokens] },
			outputTokens: usage !? { usage[\outputTokens] },
			cachedInputTokens: usage !? { usage[\cachedInputTokens] },
			cacheWriteInputTokens: usage !? { usage[\cacheWriteInputTokens] },
			usd: estimate[\usd],
			credits: estimate[\usd] !? { |usd| usd * this.creditsPerUSD },
			rateStatus: estimate[\status],
			rateReason: estimate[\reason],
			rateTable: rateTable.version ? "unavailable",
			requestId: response[\requestId],
			time: Date.getDate.asSortableString
		);
		session.add(record);
		history.add(record);
		while { history.size > maxHistory } { history.removeAt(0) };
		this.prSave;
		^record
	}

	sessionRecords { ^session.asArray }
	history { ^history.asArray }
	resetSession { session = List.new }

	clearHistory {
		history = List.new;
		if(File.exists(historyPath)) { File.delete(historyPath) };
	}

	sessionTotals { ^this.class.totalsFor(session, this.creditsPerUSD, rateTable.version) }

	*totalsFor { |records, creditsPerUSD = 100, version|
		var priced = records.select { |r| r[\usd].notNil }, usd, status = \ok;
		if(records.any { |r| r[\rateStatus] == \stale }) { status = \stale };
		if(records.any { |r| r[\rateStatus] == \missing }) { status = \missing };
		usd = if(priced.notEmpty) { priced.sum { |r| r[\usd] } };
		^(
			requests: records.size,
			inputTokens: records.sum { |r| r[\inputTokens] ? 0 },
			outputTokens: records.sum { |r| r[\outputTokens] ? 0 },
			cachedInputTokens: records.sum { |r| r[\cachedInputTokens] ? 0 },
			usd: usd,
			credits: usd !? { usd * creditsPerUSD },
			pricedRequests: priced.size,
			unpricedRequests: records.size - priced.size,
			complete: priced.size == records.size,
			rateStatus: status,
			rateTable: version
		)
	}

	prLoad {
		var json = MBProviderPaths.readJSON(historyPath), records;
		if(json.isKindOf(Dictionary).not) { ^this };
		records = json["records"];
		if(records.isKindOf(SequenceableCollection).not) { ^this };
		records.do { |item|
			var record = ();
			if(item.isKindOf(Dictionary)) {
				item.keysValuesDo { |key, value| record[key.asSymbol] = value };
				record[\provider] = record[\provider] !? (_.asSymbol);
				record[\rateStatus] = record[\rateStatus] !? (_.asSymbol);
				history.add(record);
			}
		};
	}

	prSave {
		MBProviderPaths.writeJSON(historyPath, (schema: 1, records: history.asArray));
	}
}
