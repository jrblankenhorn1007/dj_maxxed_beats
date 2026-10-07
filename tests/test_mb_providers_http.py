"""Provider adapters over the real curl transport against a loopback fake
server: request/response mapping, model lists, error mapping, timeout,
cancellation, TLS validation, non-blocking behaviour, and secret hygiene.
No live provider calls; keys are fake and live only in MBCredentialStore.fake.
"""

import json
import os
from pathlib import Path
import shutil
import subprocess
import time
import unittest

from mb_providers import processes
from mb_providers.fake_server import FakeProviderServer
from mb_providers.harness import (
    BUILD_DIR, FAKE_ANTHROPIC_KEY, FAKE_KEY, run_sclang, sc_string, tree_contains,
)

REQUEST = (
    '(model: "%MODEL%", system: "You are a DJ.", messages: ['
    '(role: \\user, content: "Make a beat \\"now\\"\\nplease"), '
    '(role: \\assistant, content: "Sure."), (role: \\user, content: "Go")], '
    'maxOutputTokens: 300, temperature: %TEMP%)'
)

PRELUDE = r"""
		var store = MBCredentialStore.fake, oa, an, req, r, h, t0, ticks = 0, ticker;
		store.storeKey(\openai, %OAKEY%, {}, {});
		store.storeKey(\anthropic, %ANKEY%, {}, {});
		0.1.wait;
		oa = MBOpenAIProvider.new(store, %BASE%, %TIMEOUT%);
		an = MBAnthropicProvider.new(store, %BASE%, %TIMEOUT%);
		~complete = { |p, req| ~await.({ |done| p.complete(req, { |x| done.(\ok, x) }, { |e| done.(\err, ~errInfo.(e)) }) }) };
		~list = { |p| ~await.({ |done| p.listModels({ |x| done.(\ok, x) }, { |e| done.(\err, ~errInfo.(e)) }) }) };
"""


def prelude(base, timeout=10):
    return (PRELUDE.replace("%OAKEY%", sc_string(FAKE_KEY))
            .replace("%ANKEY%", sc_string(FAKE_ANTHROPIC_KEY))
            .replace("%BASE%", sc_string(base))
            .replace("%TIMEOUT%", str(timeout)))


def request(model, temperature="nil"):
    return REQUEST.replace("%MODEL%", model).replace("%TEMP%", temperature)


OPENAI_RESPONSE = {
    "id": "resp_123", "object": "response", "status": "completed", "model": "gpt-5-2025-08-07",
    "output": [
        {"type": "reasoning", "id": "rs_1", "summary": []},
        {"type": "message", "role": "assistant", "content": [
            {"type": "output_text", "text": "Here is ", "annotations": []},
            {"type": "output_text", "text": "your beat \u00e9.", "annotations": []}]},
    ],
    "usage": {"input_tokens": 1200, "input_tokens_details": {"cached_tokens": 200},
              "output_tokens": 500, "output_tokens_details": {"reasoning_tokens": 100},
              "total_tokens": 1700},
}

ANTHROPIC_RESPONSE = {
    "id": "msg_01", "type": "message", "role": "assistant", "model": "claude-sonnet-4-6",
    "content": [{"type": "thinking", "thinking": "hmm", "signature": "x"},
                {"type": "text", "text": "Drop the bass."}],
    "stop_reason": "end_turn",
    "usage": {"input_tokens": 500, "cache_read_input_tokens": 400,
              "cache_creation_input_tokens": 100, "output_tokens": 50},
}


class ProviderHttpTests(unittest.TestCase):
    def run_with_server(self, name, server, body, timeout=40):
        with server:
            return run_sclang(name, body, timeout=timeout)

    def assert_no_key_leak(self, run):
        for key in (FAKE_KEY, FAKE_ANTHROPIC_KEY):
            self.assertNotIn(key, run.output)
            self.assertEqual(tree_contains(run.workdir, key), [])

    def test_openai_request_and_response_mapping(self):
        server = FakeProviderServer()
        server.route("POST", "/v1/responses", {
            "status": 200, "body": OPENAI_RESPONSE, "headers": {"x-request-id": "req_abc"}})
        snapshots = []
        server.on_request = lambda record: snapshots.append(processes.snapshot())
        body = prelude(server.base_url) + r"""
		r = ~complete.(oa, %REQ%);
		~emit.(\result, r);
		~emit.(\usage, MBUsageMeter.new(today: "2026-10-07").record(r[1]));
		""".replace("%REQ%", request("gpt-5", "0.7"))
        run = self.run_with_server("openai_complete", server, body)
        status, response = run.get("result")
        self.assertEqual(status, "ok", response)
        self.assertEqual(response["provider"], "openai")
        self.assertEqual(response["model"], "gpt-5-2025-08-07")
        self.assertEqual(response["text"], "Here is your beat \u00e9.")
        self.assertEqual(response["usage"], {"inputTokens": 1200, "outputTokens": 500,
                                             "cachedInputTokens": 200, "cacheWriteInputTokens": 0})
        self.assertEqual(response["requestId"], "req_abc")
        self.assertEqual(run.get("usage")["rateStatus"], "ok")
        [sent] = server.requests
        self.assertEqual(sent["path"], "/v1/responses")
        self.assertEqual(sent["headers"]["authorization"], "Bearer " + FAKE_KEY)
        self.assertEqual(sent["headers"]["content-type"], "application/json")
        payload = json.loads(sent["body"])
        self.assertEqual(payload, {
            "model": "gpt-5", "instructions": "You are a DJ.",
            "input": [{"role": "user", "content": "Make a beat \"now\"\nplease"},
                      {"role": "assistant", "content": "Sure."},
                      {"role": "user", "content": "Go"}],
            "max_output_tokens": 300, "temperature": 0.7, "store": False})
        self.assertTrue(snapshots)
        for snapshot in snapshots:
            self.assertNotIn(FAKE_KEY, snapshot)
        # The snapshots really cover command lines and environments.
        self.assertIn("script.scd", snapshots[0])
        self.assertIn("HOME=" + str(run.home), snapshots[0])
        self.assert_no_key_leak(run)

    def test_anthropic_request_and_response_mapping(self):
        server = FakeProviderServer()
        server.route("POST", "/v1/messages", {
            "status": 200, "body": ANTHROPIC_RESPONSE, "headers": {"request-id": "req_ant"}})
        body = prelude(server.base_url) + r"""
		~emit.(\result, ~complete.(an, %REQ%));
		""".replace("%REQ%", request("claude-sonnet-4-6"))
        run = self.run_with_server("anthropic_complete", server, body)
        status, response = run.get("result")
        self.assertEqual(status, "ok", response)
        self.assertEqual(response["text"], "Drop the bass.")
        self.assertEqual(response["usage"], {"inputTokens": 1000, "outputTokens": 50,
                                             "cachedInputTokens": 400, "cacheWriteInputTokens": 100})
        self.assertEqual(response["requestId"], "req_ant")
        self.assertEqual(response["stopReason"], "end_turn")
        [sent] = server.requests
        self.assertEqual(sent["headers"]["x-api-key"], FAKE_ANTHROPIC_KEY)
        self.assertEqual(sent["headers"]["anthropic-version"], "2023-06-01")
        self.assertNotIn("authorization", sent["headers"])
        self.assertEqual(json.loads(sent["body"]), {
            "model": "claude-sonnet-4-6", "system": "You are a DJ.", "max_tokens": 300,
            "messages": [{"role": "user", "content": "Make a beat \"now\"\nplease"},
                         {"role": "assistant", "content": "Sure."},
                         {"role": "user", "content": "Go"}]})
        self.assert_no_key_leak(run)

    def test_model_lists_label_usability_and_follow_pagination(self):
        server = FakeProviderServer()
        server.route("GET", "/v1/models", {"status": 200, "body": {"object": "list", "data": [
            {"id": "gpt-5", "object": "model", "created": 1, "owned_by": "openai"},
            {"id": "text-embedding-3-small", "object": "model", "created": 1, "owned_by": "openai"},
            {"id": "whisper-1", "object": "model", "created": 1, "owned_by": "openai"},
            {"id": "gpt-4o-mini-tts", "object": "model", "created": 1, "owned_by": "openai"},
            {"id": "o3", "object": "model", "created": 1, "owned_by": "openai"}]}},
            {"status": 200, "body": {"data": [
                {"type": "model", "id": "claude-opus-5-5", "display_name": "Claude Opus 5.5",
                 "created_at": "2026-01-01T00:00:00Z"}],
                "has_more": True, "first_id": "claude-opus-5-5", "last_id": "claude-opus-5-5"}},
            {"status": 200, "body": {"data": [
                {"type": "model", "id": "claude-haiku-4-5-20251001", "display_name": "Claude Haiku 4.5",
                 "created_at": "2025-10-01T00:00:00Z"}],
                "has_more": False, "first_id": "x", "last_id": "x"}})
        body = prelude(server.base_url) + r"""
		~emit.(\openai, ~list.(oa));
		~emit.(\anthropic, ~list.(an));
		"""
        run = self.run_with_server("models", server, body)
        status, models = run.get("openai")
        self.assertEqual(status, "ok")
        by_id = {m["id"]: m for m in models}
        self.assertEqual(sorted(by_id), sorted(["gpt-5", "text-embedding-3-small", "whisper-1",
                                                "gpt-4o-mini-tts", "o3"]))
        self.assertTrue(by_id["gpt-5"]["usable"])
        self.assertTrue(by_id["o3"]["usable"])
        for unusable in ("text-embedding-3-small", "whisper-1", "gpt-4o-mini-tts"):
            self.assertFalse(by_id[unusable]["usable"], unusable)
            self.assertTrue(by_id[unusable]["note"])
        self.assertTrue(all(m["provider"] == "openai" for m in models))
        status, models = run.get("anthropic")
        self.assertEqual(status, "ok")
        self.assertEqual([(m["id"], m["displayName"], m["usable"]) for m in models], [
            ("claude-opus-5-5", "Claude Opus 5.5", True),
            ("claude-haiku-4-5-20251001", "Claude Haiku 4.5", True)])
        openai_list, first_page, second_page = server.requests
        self.assertEqual(openai_list["headers"]["authorization"], "Bearer " + FAKE_KEY)
        self.assertIn("limit=1000", first_page["query"])
        self.assertIn("after_id=claude-opus-5-5", second_page["query"])
        self.assertEqual(second_page["headers"]["x-api-key"], FAKE_ANTHROPIC_KEY)
        self.assert_no_key_leak(run)

    def test_http_errors_map_to_error_kinds_with_redacted_detail(self):
        server = FakeProviderServer()
        leak = {"error": {"message": "Incorrect API key provided: " + FAKE_KEY + ".",
                          "type": "invalid_request_error", "code": "invalid_api_key"}}
        server.route("POST", "/v1/responses",
                     {"status": 401, "body": leak},
                     {"status": 429, "body": {"error": {"message": "Rate limit reached", "type": "requests"}},
                      "headers": {"retry-after": "7"}},
                     {"status": 500, "body": "<html>oops</html>"},
                     {"status": 404, "body": {"error": {"message": "The model `gpt-x` does not exist",
                                                        "code": "model_not_found"}}},
                     {"status": 400, "body": {"error": {"message": "Unsupported parameter: temperature"}}},
                     {"status": 200, "body": "{not json"},
                     {"status": 200, "body": {"id": "r", "status": "completed", "output": []}},
                     {"status": 403, "body": {"error": {"message": "forbidden"}}})
        server.route("POST", "/v1/messages",
                     {"status": 529, "body": {"type": "error", "error": {"type": "overloaded_error",
                                                                          "message": "Overloaded"}}},
                     {"status": 404, "body": {"type": "error", "error": {"type": "not_found_error",
                                                                          "message": "model: claude-x"}}},
                     {"status": 401, "body": {"type": "error", "error": {
                         "type": "authentication_error", "message": "invalid x-api-key " + FAKE_ANTHROPIC_KEY}}})
        body = prelude(server.base_url) + r"""
		~out = List.new;
		8.do { ~out.add(~complete.(oa, %OAREQ%)) };
		3.do { ~out.add(~complete.(an, %ANREQ%)) };
		store.removeKey(\openai, {}, {});
		0.1.wait;
		~out.add(~complete.(oa, %OAREQ%));
		~out.add(~complete.(oa, %OAREQ%.put(\maxOutputTokens, 0)));
		~emit.(\errors, ~out.asArray);
		""".replace("%OAREQ%", request("gpt-5")).replace("%ANREQ%", request("claude-x"))
        run = self.run_with_server("errors", server, body)
        errors = run.get("errors")
        self.assertTrue(all(status == "err" for status, _ in errors), errors)
        kinds = [error["kind"] for _, error in errors]
        self.assertEqual(kinds, ["auth", "rateLimit", "server", "unavailableModel", "validation",
                                 "parse", "parse", "auth", "server", "unavailableModel", "auth",
                                 "auth", "validation"])
        details = [error["detail"] for _, error in errors]
        self.assertIn("HTTP 401", details[0])
        self.assertIn("7", details[1])
        self.assertIn("HTTP 500", details[2])
        self.assertIn("Unsupported parameter", details[4])
        self.assertIn("Overloaded", details[8])
        self.assertIn("No API key", details[11])
        self.assertEqual(len(server.requests), 11)
        self.assert_no_key_leak(run)

    def test_requests_are_non_blocking_and_time_out(self):
        server = FakeProviderServer()
        server.route("POST", "/v1/responses", {"status": 200, "body": OPENAI_RESPONSE, "delay": 4})
        body = prelude(server.base_url, timeout=1.5) + r"""
		ticker = Routine({ loop { ticks = ticks + 1; 0.05.wait } }).play(AppClock);
		t0 = ~elapsed.();
		r = ~await.({ |done|
			oa.complete(%REQ%, { |x| done.(\ok, x) }, { |e| done.(\err, ~errInfo.(e)) });
			~emit.(\returnedAfter, ~elapsed.() - t0);
		});
		ticker.stop;
		~emit.(\result, r);
		~emit.(\elapsed, ~elapsed.() - t0);
		~emit.(\ticks, ticks);
		""".replace("%REQ%", request("gpt-5"))
        run = self.run_with_server("timeout", server, body)
        self.assertLess(run.get("returnedAfter"), 0.2)
        status, error = run.get("result")
        self.assertEqual(status, "err")
        self.assertEqual(error["kind"], "network")
        self.assertIn("timed out", error["detail"])
        self.assertGreater(run.get("elapsed"), 1.3)
        self.assertLess(run.get("elapsed"), 3.9)
        # A blocked interpreter would tick ~0 times; hosted runners schedule
        # AppClock coarsely, so require a quarter of the nominal 50 ms ticks.
        self.assertGreater(run.get("ticks"), max(5, run.get("elapsed") / 0.05 * 0.25))

    def test_cancel_stops_the_request_promptly(self):
        server = FakeProviderServer()
        server.route("POST", "/v1/responses", {"status": 200, "body": OPENAI_RESPONSE, "delay": 5})
        body = prelude(server.base_url) + r"""
		~calls = 0;
		t0 = ~elapsed.();
		r = ~await.({ |done|
			h = oa.complete(%REQ%, { |x| ~calls = ~calls + 1; done.(\ok) }, { |e| ~calls = ~calls + 1; done.(\err, ~errInfo.(e)) });
			AppClock.sched(0.5, { h.cancel; nil });
		});
		~emit.(\result, r);
		~emit.(\elapsed, ~elapsed.() - t0);
		~emit.(\handle, [h.isCancelled, h.isDone]);
		1.0.wait;
		h.cancel;
		~emit.(\calls, ~calls);
		""".replace("%REQ%", request("gpt-5"))
        run = self.run_with_server("cancel", server, body)
        status, error = run.get("result")
        self.assertEqual(status, "err")
        self.assertEqual(error["kind"], "cancelled")
        self.assertLess(run.get("elapsed"), 1.5)
        self.assertEqual(run.get("handle"), [True, True])
        self.assertEqual(run.get("calls"), 1)
        lingering = processes.command_lines()
        self.assertIn("python", lingering.lower())
        self.assertNotIn("127.0.0.1:{}".format(server.port), lingering)

    @unittest.skipUnless(shutil.which("openssl"), "openssl CLI required for a self-signed cert")
    def test_tls_certificate_validation_is_enforced(self):
        cert_dir = BUILD_DIR / "tls-cert"
        cert_dir.mkdir(parents=True, exist_ok=True)
        cert, key = cert_dir / "cert.pem", cert_dir / "key.pem"
        subprocess.run(["openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes", "-keyout",
                        str(key), "-out", str(cert), "-days", "1", "-subj", "/CN=127.0.0.1"],
                       check=True, capture_output=True)
        server = FakeProviderServer(certfile=str(cert), keyfile=str(key))
        server.route("POST", "/v1/responses", {"status": 200, "body": OPENAI_RESPONSE})
        body = prelude(server.base_url) + r"""
		~emit.(\result, ~complete.(oa, %REQ%));
		~emit.(\plainRemote, ~complete.(MBOpenAIProvider.new(store, "http://example.com"), %REQ%));
		""".replace("%REQ%", request("gpt-5"))
        run = self.run_with_server("tls", server, body)
        status, error = run.get("result")
        self.assertEqual(status, "err")
        self.assertEqual(error["kind"], "network")
        self.assertIn("TLS", error["detail"])
        self.assertEqual(server.requests, [])
        self.assertEqual(run.get("plainRemote")[1]["kind"], "config")
        self.assert_no_key_leak(run)

    def test_validate_key_uses_the_model_list(self):
        server = FakeProviderServer()
        server.route("GET", "/v1/models",
                     {"status": 200, "body": {"data": [{"id": "gpt-5", "object": "model"}]}},
                     {"status": 401, "body": {"error": {"message": "bad key"}}})
        body = prelude(server.base_url) + r"""
		~emit.(\ok, ~await.({ |done| store.validateKey(\openai, { |m| done.(\ok, m.size) }, { |e| done.(\err, ~errInfo.(e)) }, oa) }));
		~emit.(\bad, ~await.({ |done| store.validateKey(\openai, { |m| done.(\ok) }, { |e| done.(\err, ~errInfo.(e)) }, oa) }));
		"""
        run = self.run_with_server("validate", server, body)
        self.assertEqual(run.get("ok"), ["ok", 1])
        self.assertEqual(run.get("bad")[1]["kind"], "auth")
        self.assert_no_key_leak(run)


if __name__ == "__main__":
    unittest.main()
