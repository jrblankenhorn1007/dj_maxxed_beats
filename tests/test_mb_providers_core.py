"""Offline provider-layer tests: JSON, redaction, usage/cost, catalog,
credential fake, mock provider, and registry. No network, no real keys."""

import datetime
import json
import os
import unittest

from mb_providers.harness import (
    FAKE_KEY, RATES_PATH, fresh_workdir, run_sclang, sc_string, tree_contains,
)


def load_rates():
    with RATES_PATH.open(encoding="utf-8") as handle:
        return json.load(handle)


class RateTableSchemaTests(unittest.TestCase):
    def test_rate_table_is_versioned_sourced_and_never_zero_for_paid_providers(self):
        table = load_rates()
        self.assertEqual(table["schema"], 1)
        self.assertTrue(table["version"])
        datetime.date.fromisoformat(table["retrieved"])
        self.assertEqual(table["creditsPerUSD"], 100)
        self.assertGreater(table["staleAfterDays"], 0)
        official = {
            "openai": "https://developers.openai.com/",
            "anthropic": "https://platform.claude.com/",
        }
        for provider, prefix in official.items():
            entry = table["providers"][provider]
            self.assertTrue(entry["source"].startswith(prefix), entry["source"])
            datetime.date.fromisoformat(entry["retrieved"])
            self.assertTrue(entry["models"])
            for model, rates in entry["models"].items():
                for field in ("input", "output"):
                    self.assertGreater(rates[field], 0, (model, field))
                for field in ("cachedInput", "cacheWrite", "cacheWrite1h"):
                    if field in rates:
                        self.assertGreater(rates[field], 0, (model, field))
        mock = table["providers"]["mock"]["models"]["mock-composer-1"]
        self.assertEqual(mock["input"], 0)


class JsonAndRedactionTests(unittest.TestCase):
    def test_json_parse_encode_round_trip_and_malformed_input(self):
        workdir = fresh_workdir("json")
        document = {
            "s": "caf\u00e9 \U0001f3b5 \"q\" \\ /\n\t",
            "i": 42, "neg": -7, "f": 1.5, "e": 2.5e-3, "big": 9999999999,
            "t": True, "fl": False, "n": None,
            "arr": [1, "two", [3], {"k": "v"}], "empty": {}, "ea": [],
        }
        (workdir / "doc.json").write_text(
            json.dumps(document, ensure_ascii=True), encoding="utf-8")
        malformed = ['{"a":', '[1,2', '{"a" 1}', 'tru', '"unterminated',
                     '{"a":1}x', '', '{"a":"\\x"}', '01', '[1,]']
        (workdir / "bad.json").write_text(json.dumps(malformed), encoding="utf-8")
        body = r"""
		var dir = %DIR%, doc, bad;
		doc = MBJSON.parse(File.readAllString(dir +/+ "doc.json"));
		~emit.(\roundTrip, doc);
		~emit.(\types, [doc["i"].class.name, doc["f"].class.name, doc["big"].class.name,
			doc["t"].class.name, doc.includesKey("n")]);
		bad = MBJSON.parse(File.readAllString(dir +/+ "bad.json"));
		~emit.(\malformed, bad.collect { |text|
			try { MBJSON.parse(text); \accepted } { |e| ~errInfo.(e)[\kind] }
		});
		""".replace("%DIR%", sc_string(str(workdir)))
        run = run_sclang("json", body, workdir=workdir)
        expected = dict(document)
        del expected["n"]
        self.assertEqual(run.get("roundTrip"), expected)
        self.assertEqual(run.get("types"),
                         ["Integer", "Float", "Float", "True", False])
        self.assertEqual(run.get("malformed"), ["parse"] * len(malformed))

    def test_redaction_removes_key_shapes_and_known_secrets(self):
        body = r"""
		var key = %KEY%;
		~emit.(\samples, [
			MBRedact.string("Incorrect API key provided: " ++ key ++ "."),
			MBRedact.string("Authorization: Bearer " ++ key),
			MBRedact.string("x-api-key: " ++ key ++ "\nnext"),
			MBRedact.string("custom secret abcXYZ123 here", ["abcXYZ123"]),
			MBRedact.string("nothing secret here"),
			MBRedact.string("sk-ant-api03-AbCdEf_0123456789")
		]);
		""".replace("%KEY%", sc_string(FAKE_KEY))
        run = run_sclang("redact", body)
        samples = run.get("samples")
        for text in samples:
            self.assertNotIn(FAKE_KEY, text)
            self.assertNotIn("abcXYZ123", text)
            self.assertNotIn("AbCdEf_0123456789", text)
        self.assertIn("[REDACTED]", samples[0])
        self.assertEqual(samples[4], "nothing secret here")
        self.assertIn("next", samples[2])
        self.assertNotIn(FAKE_KEY, run.output)


class UsageMeterTests(unittest.TestCase):
    def test_non_date_alias_matches_by_string_value(self):
        workdir = fresh_workdir("rate_alias")
        rates = load_rates()
        rates["providers"]["openai"]["models"]["gpt-5"]["aliases"] = ["dj-latest"]
        path = workdir / "rates.json"
        path.write_text(json.dumps(rates), encoding="utf-8")
        body = r"""
		var table = MBRateTable.new(%PATH%), alias = "dj-" ++ "latest";
		~emit.(\lookup, table.lookup(\openai, alias));
		~emit.(\estimate, table.estimate(\openai, alias,
			(inputTokens: 1000, outputTokens: 100), "2026-10-07"));
		""".replace("%PATH%", sc_string(str(path)))
        run = run_sclang("rate_alias", body, workdir=workdir)
        self.assertIsNotNone(run.get("lookup"))
        self.assertEqual(run.get("lookup")[0], "gpt-5")
        estimate = run.get("estimate")
        self.assertEqual(estimate["matchedModel"], "gpt-5")
        self.assertEqual(estimate["status"], "ok")
        gpt5 = rates["providers"]["openai"]["models"]["gpt-5"]
        self.assertAlmostEqual(estimate["usd"],
                               (1000 * gpt5["input"] + 100 * gpt5["output"]) / 1e6)

    def test_usage_estimates_session_totals_history_and_missing_or_stale_rates(self):
        rates = load_rates()
        workdir = fresh_workdir("usage")
        body = r"""
		var meter, again, rec, stale, recs = List.new;
		meter = MBUsageMeter.new(today: "2026-10-07");
		rec = { |provider, model, usage| meter.record((provider: provider, model: model,
			text: "x", usage: usage, requestId: "req-" ++ model)) };
		recs.add(rec.(\openai, "gpt-5", (inputTokens: 1200, outputTokens: 500, cachedInputTokens: 200)));
		recs.add(rec.(\openai, "gpt-5-2025-08-07", (inputTokens: 1000, outputTokens: 100, cachedInputTokens: 0)));
		recs.add(rec.(\anthropic, "claude-sonnet-4-6", (inputTokens: 1000, outputTokens: 50,
			cachedInputTokens: 400, cacheWriteInputTokens: 100)));
		recs.add(rec.(\openai, "gpt-5.4", (inputTokens: 300000, outputTokens: 1000, cachedInputTokens: 0)));
		recs.add(rec.(\openai, "not-a-real-model", (inputTokens: 10, outputTokens: 10, cachedInputTokens: 0)));
		recs.add(rec.(\openai, "gpt-5-pro", (inputTokens: 10, outputTokens: 10, cachedInputTokens: 5)));
		recs.add(rec.(\anthropic, "claude-haiku-4-5-20251001", nil));
		recs.add(rec.(\mock, "mock-composer-1", (inputTokens: 10, outputTokens: 10, cachedInputTokens: 0)));
		~emit.(\records, recs.asArray);
		~emit.(\totals, meter.sessionTotals);
		again = MBUsageMeter.new(today: "2026-10-07");
		~emit.(\historySize, again.history.size);
		~emit.(\againTotals, again.sessionTotals);
		stale = MBUsageMeter.new(today: "2027-06-01");
		~emit.(\stale, stale.record((provider: \openai, model: "gpt-5", text: "",
			usage: (inputTokens: 1000, outputTokens: 0, cachedInputTokens: 0))));
		~emit.(\promoStale, MBUsageMeter.new(today: "2026-11-22").record((provider: \openai,
			model: "gpt-5.6-sol", text: "", usage: (inputTokens: 1000, outputTokens: 0, cachedInputTokens: 0))));
		~emit.(\historyFile, File.exists(meter.historyPath));
		again.clearHistory;
		~emit.(\cleared, [again.history.size, MBUsageMeter.new.history.size, File.exists(meter.historyPath)]);
		"""
        run = run_sclang("usage", body, workdir=workdir)
        records = run.get("records")
        oa = rates["providers"]["openai"]["models"]
        an = rates["providers"]["anthropic"]["models"]

        def approx(actual, expected):
            self.assertIsNotNone(actual)
            self.assertAlmostEqual(actual, expected, places=12)

        gpt5 = oa["gpt-5"]
        usd = (1000 * gpt5["input"] + 200 * gpt5["cachedInput"] + 500 * gpt5["output"]) / 1e6
        approx(records[0]["usd"], usd)
        approx(records[0]["credits"], usd * 100)
        self.assertEqual(records[0]["rateStatus"], "ok")
        self.assertEqual(records[0]["rateTable"], rates["version"])
        self.assertEqual(records[0]["cachedInputTokens"], 200)
        approx(records[1]["usd"], (1000 * gpt5["input"] + 100 * gpt5["output"]) / 1e6)
        son = an["claude-sonnet-4-6"]
        approx(records[2]["usd"], (500 * son["input"] + 400 * son["cachedInput"]
                                   + 100 * son["cacheWrite"] + 50 * son["output"]) / 1e6)
        long_rates = oa["gpt-5.4"]["longContext"]
        approx(records[3]["usd"], (300000 * long_rates["input"] + 1000 * long_rates["output"]) / 1e6)
        for index in (4, 5, 6):
            self.assertIsNone(records[index].get("usd"), records[index])
            self.assertIsNone(records[index].get("credits"))
            self.assertEqual(records[index]["rateStatus"], "missing")
        self.assertEqual(records[7]["usd"], 0)
        self.assertEqual(records[7]["rateStatus"], "ok")

        totals = run.get("totals")
        self.assertEqual(totals["requests"], 8)
        self.assertEqual(totals["unpricedRequests"], 3)
        self.assertEqual(totals["pricedRequests"], 5)
        self.assertFalse(totals["complete"])
        self.assertEqual(totals["rateStatus"], "missing")
        priced = sum(r["usd"] for r in records if r.get("usd") is not None)
        approx(totals["usd"], priced)
        approx(totals["credits"], priced * 100)
        self.assertEqual(totals["inputTokens"], 1200 + 1000 + 1000 + 300000 + 10 + 10 + 10)

        self.assertEqual(run.get("historySize"), 8)
        self.assertEqual(run.get("againTotals")["requests"], 0)
        self.assertIsNone(run.get("againTotals").get("usd"))
        stale = run.get("stale")
        self.assertEqual(stale["rateStatus"], "stale")
        approx(stale["usd"], 1000 * gpt5["input"] / 1e6)
        self.assertEqual(run.get("promoStale")["rateStatus"], "stale")
        self.assertTrue(run.get("historyFile"))
        self.assertEqual(run.get("cleared"), [0, 0, False])


class CatalogTests(unittest.TestCase):
    def test_refresh_persist_select_stale_and_unavailable(self):
        workdir = fresh_workdir("catalog")
        body = r"""
		var mock = MBMockProvider.new, reg, cat, cat2, r, now = 1000000;
		reg = MBProviderRegistry.new(MBCredentialStore.fake, [mock]);
		cat = MBModelCatalog.new(reg, clock: { now });
		~emit.(\initial, [cat.models(\mock).size, cat.lastRefreshed(\mock), cat.isStale(\mock), cat.selectedModel(\mock)]);
		~emit.(\noSelection, ~errInfo.(cat.checkSelection(\mock)));
		r = ~await.({ |done| cat.refresh(\mock, { |m| done.(\ok, m) }, { |e| done.(\err, e) }) });
		~emit.(\refresh, [r[0], r[1].collect(_.id)]);
		~emit.(\afterRefresh, [cat.lastRefreshed(\mock), cat.isStale(\mock)]);
		~emit.(\selectBad, ~errInfo.(cat.selectModel(\mock, "no-such-model")));
		~emit.(\selectUnusable, ~errInfo.(cat.selectModel(\mock, "mock-legacy-0")));
		~emit.(\selectGood, cat.selectModel(\mock, "mock-composer-1"));
		~emit.(\check, cat.checkSelection(\mock));
		now = now + (25 * 3600);
		cat2 = MBModelCatalog.new(reg, clock: { now });
		~emit.(\persisted, [cat2.selectedModel(\mock), cat2.models(\mock).collect(_.id), cat2.isStale(\mock)]);
		mock.listModelsError = MBError(\network, "offline");
		r = ~await.({ |done| cat2.refresh(\mock, { |m| done.(\ok, m) }, { |e| done.(\err, e) }) });
		~emit.(\failedRefresh, [r[0], ~errInfo.(r[1]), cat2.models(\mock).size, cat2.isStale(\mock),
			~errInfo.(cat2.lastError(\mock))]);
		mock.listModelsError = nil;
		mock.models = [(id: "mock-composer-2", displayName: "Mock Composer 2", provider: \mock, usable: true, note: "")];
		r = ~await.({ |done| cat2.refresh(\mock, { |m| done.(\ok, m) }, { |e| done.(\err, e) }) });
		~emit.(\gone, [cat2.selectedModel(\mock), ~errInfo.(cat2.checkSelection(\mock)), cat2.isStale(\mock)]);
		~emit.(\unknownProvider, ~await.({ |done| cat2.refresh(\nope, { |m| done.(\ok) }, { |e| done.(\err, ~errInfo.(e)) }) }));
		~emit.(\files, [cat.settingsPath, cat.cachePath]);
		"""
        run = run_sclang("catalog", body, workdir=workdir)
        self.assertEqual(run.get("initial"), [0, None, False, None])
        self.assertEqual(run.get("noSelection")["kind"], "unavailableModel")
        self.assertEqual(run.get("refresh"), ["ok", ["mock-composer-1", "mock-legacy-0"]])
        self.assertEqual(run.get("afterRefresh"), [1000000, False])
        self.assertEqual(run.get("selectBad")["kind"], "unavailableModel")
        self.assertEqual(run.get("selectUnusable")["kind"], "unavailableModel")
        self.assertIsNone(run.get("selectGood"))
        self.assertIsNone(run.get("check"))
        self.assertEqual(run.get("persisted"),
                         ["mock-composer-1", ["mock-composer-1", "mock-legacy-0"], True])
        failed = run.get("failedRefresh")
        self.assertEqual(failed[0], "err")
        self.assertEqual(failed[1]["kind"], "network")
        self.assertEqual(failed[2], 2)
        self.assertTrue(failed[3])
        self.assertEqual(failed[4]["kind"], "network")
        gone = run.get("gone")
        self.assertEqual(gone[0], "mock-composer-1")
        self.assertEqual(gone[1]["kind"], "unavailableModel")
        self.assertFalse(gone[2])
        self.assertEqual(run.get("unknownProvider"), ["err", {"kind": "config",
                         "detail": run.get("unknownProvider")[1]["detail"]}])
        settings_path, cache_path = run.get("files")
        self.assertTrue(os.path.normcase(os.path.normpath(settings_path)).startswith(
            os.path.normcase(os.path.normpath(str(run.home)))))
        with open(settings_path, encoding="utf-8") as handle:
            settings = json.load(handle)
        self.assertEqual(settings["selectedModels"]["mock"], "mock-composer-1")
        with open(cache_path, encoding="utf-8") as handle:
            self.assertIn("mock-composer-2", handle.read())


class CredentialAndMockTests(unittest.TestCase):
    def test_fake_credential_store_lifecycle_never_reveals_key(self):
        body = r"""
		var store = MBCredentialStore.fake, key = %KEY%, r;
		~emit.(\has0, ~await.({ |done| store.hasKey(\openai, done) }));
		r = ~await.({ |done| store.storeKey(\openai, key, { done.(\ok) }, { |e| done.(\err, e) }) });
		~emit.(\stored, r[0]);
		~emit.(\has1, ~await.({ |done| store.hasKey(\openai, done) }));
		~emit.(\hasOther, ~await.({ |done| store.hasKey(\anthropic, done) }));
		r = ~await.({ |done| store.storeKey(\anthropic, "bad key\"" ++ key, { done.(\ok) }, { |e| done.(\err, ~errInfo.(e)) }) });
		~emit.(\invalid, r);
		r = ~await.({ |done| store.storeKey(\nope, key, { done.(\ok) }, { |e| done.(\err, ~errInfo.(e)) }) });
		~emit.(\unknownId, r);
		~emit.(\describe, store.asString);
		r = ~await.({ |done| store.removeKey(\openai, { done.(\ok) }, { |e| done.(\err, e) }) });
		~emit.(\removed, r[0]);
		~emit.(\has2, ~await.({ |done| store.hasKey(\openai, done) }));
		r = ~await.({ |done| store.validateKey(\openai, { done.(\ok) }, { |e| done.(\err, ~errInfo.(e)) }) });
		~emit.(\validateMissing, r);
		store.storeKey(\openai, key, {}, {});
		("posting store: " ++ store).postln;
		""".replace("%KEY%", sc_string(FAKE_KEY))
        run = run_sclang("credfake", body)
        self.assertEqual(run.get("has0"), [False])
        self.assertEqual(run.get("stored"), "ok")
        self.assertEqual(run.get("has1"), [True])
        self.assertEqual(run.get("hasOther"), [False])
        self.assertEqual(run.get("invalid")[0], "err")
        self.assertEqual(run.get("invalid")[1]["kind"], "validation")
        self.assertEqual(run.get("unknownId")[1]["kind"], "config")
        self.assertEqual(run.get("removed"), "ok")
        self.assertEqual(run.get("has2"), [False])
        self.assertEqual(run.get("validateMissing")[1]["kind"], "auth")
        self.assertNotIn(FAKE_KEY, run.output)
        self.assertNotIn(FAKE_KEY[8:], run.output)
        self.assertEqual(tree_contains(run.workdir, FAKE_KEY), [])

    def test_mock_provider_is_deterministic_cancellable_and_scriptable(self):
        body = r"""
		var mock = MBMockProvider.new, req, a, b, c, h, r, t0;
		req = (model: "mock-composer-1", system: "sys", messages: [(role: \user, content: "make a beat")],
			maxOutputTokens: 256, temperature: nil);
		a = ~await.({ |done| mock.complete(req, { |x| done.(x) }, { |e| done.(e) }) })[0];
		b = ~await.({ |done| mock.complete(req, { |x| done.(x) }, { |e| done.(e) }) })[0];
		c = ~await.({ |done| mock.complete(req.copy.put(\messages, [(role: \user, content: "other")]),
			{ |x| done.(x) }, { |e| done.(e) }) })[0];
		~emit.(\a, a); ~emit.(\sameText, a.text == b.text); ~emit.(\differs, a.text != c.text);
		~emit.(\models, ~await.({ |done| mock.listModels(done, done) })[0]);
		mock.latency = 0.5;
		r = ~await.({ |done| h = mock.complete(req, { |x| done.(\ok) }, { |e| done.(\err, ~errInfo.(e)) }); h.cancel });
		~emit.(\cancelled, r);
		mock.latency = 0;
		mock.enqueue(MBError(\rateLimit, "scripted"));
		mock.enqueue("scripted text");
		~emit.(\scriptErr, ~await.({ |done| mock.complete(req, { |x| done.(\ok) }, { |e| done.(\err, ~errInfo.(e)) }) }));
		~emit.(\scriptOk, ~await.({ |done| mock.complete(req, { |x| done.(\ok, x.text) }, { |e| done.(\err) }) }));
		~emit.(\badModel, ~await.({ |done| mock.complete(req.copy.put(\model, "gpt-x"), { done.(\ok) }, { |e| done.(\err, ~errInfo.(e)) }) }));
		~emit.(\invalid, ~await.({ |done| mock.complete(req.copy.put(\messages, []), { done.(\ok) }, { |e| done.(\err, ~errInfo.(e)) }) }));
		~emit.(\registry, [MBProviderRegistry.default.providers.collect(_.id), MBProviderRegistry.default.at(\anthropic).displayName,
			MBProviderRegistry.default.at(\mock).displayName, MBProviderRegistry.default.at(\nope)]);
		"""
        run = run_sclang("mock", body)
        a = run.get("a")
        self.assertEqual(a["provider"], "mock")
        self.assertEqual(a["model"], "mock-composer-1")
        self.assertTrue(a["text"])
        self.assertGreater(a["usage"]["inputTokens"], 0)
        self.assertEqual(a["usage"]["cachedInputTokens"], 0)
        self.assertTrue(a["requestId"].startswith("mock-"))
        self.assertTrue(run.get("sameText"))
        self.assertTrue(run.get("differs"))
        models = run.get("models")
        self.assertEqual(models[0]["id"], "mock-composer-1")
        self.assertEqual(models[0]["provider"], "mock")
        self.assertTrue(models[0]["usable"])
        self.assertEqual(run.get("cancelled"), ["err", {"kind": "cancelled",
                         "detail": run.get("cancelled")[1]["detail"]}])
        self.assertEqual(run.get("scriptErr")[1]["kind"], "rateLimit")
        self.assertEqual(run.get("scriptOk"), ["ok", "scripted text"])
        self.assertEqual(run.get("badModel")[1]["kind"], "unavailableModel")
        self.assertEqual(run.get("invalid")[1]["kind"], "validation")
        self.assertEqual(run.get("registry"),
                         [["openai", "anthropic", "mock"], "Anthropic (Claude)",
                          "Mock DJ (offline)", None])


class ProcessRunnerTests(unittest.TestCase):
    """MBProcess reports exit codes, enforces its watchdog timeout, and stays
    cancellable on every platform (Windows: argv + exit-code file polling)."""

    def test_normal_helper_exits_leave_clock_responsive_without_cleanup_errors(self):
        body = r"""
		var quick, target = "MaxxedBeatsTest-" ++ 100000000.rand ++ ":openai",
			ticks = 0, ticker, results = List.new;
		quick = if(MBProviderPaths.isWindows) {
			MBProviderPaths.windowsHelperArgv("has", ["-Target", target])
		} { "exit 1" };
		ticker = Routine { loop { ticks = ticks + 1; 0.05.wait } }.play(AppClock);
		3.do {
			var dir = MBProviderPaths.newRunDir;
			results.add(~await.({ |done| MBProcess.run(quick, dir, nil, 30, done) }));
			MBProviderPaths.removeDir(dir);
		};
		// Let every deferred pipe close run while the interpreter is still alive.
		4.wait;
		ticker.stop;
		~emit.(\results, results.asArray);
		~emit.(\ticks, ticks);
		~emit.(\target, target);
		"""
        run = run_sclang("process_normal_exit", body, timeout=60)
        self.assertEqual(run.get("results"), [[1, "exited"]] * 3)
        self.assertGreater(run.get("ticks"), 20)
        self.assertNotIn("ERROR:", run.output)
        from mb_providers import processes
        self.assertNotIn(run.get("target"), processes.command_lines())

    def test_exit_code_watchdog_timeout_and_cancel(self):
        body = r"""
		var dir = MBProviderPaths.newRunDir, slow, quick, t0, run;
		if(MBProviderPaths.isWindows) {
			// The real helper: an absent, test-only credential exits with 1.
			quick = MBProviderPaths.windowsHelperArgv("has", ["-Target", "MaxxedBeatsTest-" ++ 100000000.rand ++ ":openai"]);
			slow = [MBProviderPaths.powershellPath, "-NoLogo", "-NoProfile", "-NonInteractive", "-InputFormat", "None",
				"-Command", "Start-Sleep -Seconds 20"];
		} {
			quick = "exit 1";
			slow = "sleep 20";
		};
		run = { |script, timeout, cancelAfter|
			var calls = 0, p;
			t0 = ~elapsed.();
			~await.({ |done|
				p = MBProcess.run(script, MBProviderPaths.newRunDir, nil, timeout, { |code, why|
					calls = calls + 1; done.(code, why, ~elapsed.() - t0) });
				cancelAfter !? { AppClock.sched(cancelAfter, { p.cancel; nil }) };
			}) ++ [{ 1.0.wait; calls }.value]
		};
		~emit.(\quick, run.(quick, 60));
		~emit.(\timeout, run.(slow, 2));
		~emit.(\cancel, run.(slow, 60, 0.5));
		"""
        run = run_sclang("process_runner", body, timeout=120)
        code, why, elapsed, calls = run.get("quick")
        self.assertEqual((code, why, calls), (1, "exited", 1))
        self.assertLess(elapsed, 30)
        code, why, elapsed, calls = run.get("timeout")
        self.assertEqual((code, why, calls), (None, "timeout", 1))
        self.assertGreater(elapsed, 1.9)
        self.assertLess(elapsed, 6)
        code, why, elapsed, calls = run.get("cancel")
        self.assertEqual((code, why, calls), (None, "cancelled", 1))
        self.assertLess(elapsed, 2)


class PlatformBackendCommandTests(unittest.TestCase):
    def test_backend_commands_never_carry_the_key(self):
        body = r"""
		var key = %KEY%, out = List.new;
		[MBKeychainCredentialStore.new, MBKeychainCredentialStore.new("/x/test.keychain-db"),
			MBSecretServiceCredentialStore.new, MBWindowsCredentialStore.new].do { |s|
			out.add((name: s.class.name, prelude: s.keyPrelude(\openai, "/x/k.fifo"),
				payloadHasKey: s.keyPayload(\openai).notNil,
				store: s.storeCommand(\openai, "/x/k.fifo"),
				storePayloadHasKey: s.storePayload(\openai, key).find(key).notNil,
				has: s.hasCommand(\openai), remove: s.removeCommand(\openai)));
		};
		~emit.(\backends, out.asArray);
		""".replace("%KEY%", sc_string(FAKE_KEY))
        run = run_sclang("backends", body)
        backends = run.get("backends")
        self.assertEqual(len(backends), 4)
        for backend in backends:
            for field in ("prelude", "store", "has", "remove"):
                # POSIX backends answer shell text, Windows an argv list.
                if isinstance(backend[field], list):
                    backend[field] = " ".join(backend[field])
                self.assertNotIn(FAKE_KEY, backend[field], (backend["name"], field))
            self.assertFalse(backend["payloadHasKey"])
            self.assertTrue(backend["storePayloadHasKey"])
        self.assertIn("security find-generic-password", backends[0]["prelude"])
        self.assertIn("/x/test.keychain-db", backends[1]["prelude"])
        self.assertIn("secret-tool lookup", backends[2]["prelude"])
        self.assertIn("MaxxedBeatsCredential.ps1", backends[3]["prelude"])
        self.assertIn("-Target MaxxedBeats:openai", backends[3]["prelude"])
        self.assertIn("-Action store", backends[3]["store"])


if __name__ == "__main__":
    unittest.main()
