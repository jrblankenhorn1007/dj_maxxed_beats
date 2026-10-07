"""Windows Credential Manager backend round trip (the Windows counterpart of
test_mb_providers_keychain.py).

Uses real generic credentials under a unique, test-only target prefix
(MaxxedBeatsTest-<random>:openai / :anthropic); the production targets
(MaxxedBeats:<id>) are never touched, and both test targets are deleted
after the test whatever happens. The key reaches curl.exe only through the
PowerShell helper's pipe to curl's stdin: process command lines and
environments are checked while the fake server holds a request.
"""

import subprocess
import sys
import unittest
import uuid

from mb_providers import processes
from mb_providers.fake_server import FakeProviderServer
from mb_providers.harness import (
    FAKE_ANTHROPIC_KEY, FAKE_KEY, fresh_workdir, run_sclang, sc_string, tree_contains,
)


def cmdkey(*args):
    return subprocess.run(["cmdkey"] + list(args), capture_output=True, text=True)


@unittest.skipUnless(sys.platform == "win32", "Windows Credential Manager backend (Windows only)")
class WindowsCredentialManagerTests(unittest.TestCase):
    def setUp(self):
        self.prefix = "MaxxedBeatsTest-" + uuid.uuid4().hex[:16]
        self.targets = [self.prefix + ":openai", self.prefix + ":anthropic"]
        self.addCleanup(self.delete_test_targets)
        self.workdir = fresh_workdir("wincred")

    def delete_test_targets(self):
        for target in self.targets:
            cmdkey("/delete:" + target)
        for target in self.targets:
            self.assertNotIn(target, cmdkey("/list:" + target).stdout)

    def test_store_use_validate_and_remove_key_in_credential_manager(self):
        server = FakeProviderServer()
        server.route("GET", "/v1/models", {"status": 200, "body": {"data": [{"id": "gpt-5"}]}})
        snapshots = []
        listed = []

        def on_request(record):
            snapshots.append(processes.snapshot())
            listed.append(cmdkey("/list:" + self.targets[0]).stdout)

        server.on_request = on_request
        body = r"""
		var store = MBWindowsCredentialStore.new(%PREFIX%), oa, an;
		oa = MBOpenAIProvider.new(store, %BASE%, 10);
		an = MBAnthropicProvider.new(store, %BASE%, 10);
		~emit.(\backend, [store.backendName, store.target(\openai)]);
		~emit.(\has0, ~await.({ |done| store.hasKey(\openai, done) }));
		~emit.(\remove0, ~await.({ |done| store.removeKey(\openai, { done.(\ok) }, { |e| done.(\err, ~errInfo.(e)) }) }));
		~emit.(\store, ~await.({ |done| store.storeKey(\openai, %KEY%, { done.(\ok) }, { |e| done.(\err, ~errInfo.(e)) }) }));
		~emit.(\replace, ~await.({ |done| store.storeKey(\openai, %KEY%, { done.(\ok) }, { |e| done.(\err, ~errInfo.(e)) }) }));
		~emit.(\has1, ~await.({ |done| store.hasKey(\openai, done) }));
		~emit.(\hasOther, ~await.({ |done| store.hasKey(\anthropic, done) }));
		~emit.(\validate, ~await.({ |done| store.validateKey(\openai, { |m| done.(\ok, m.size) }, { |e| done.(\err, ~errInfo.(e)) }, oa) }));
		~emit.(\storeOther, ~await.({ |done| store.storeKey(\anthropic, %ANKEY%, { done.(\ok) }, { |e| done.(\err, ~errInfo.(e)) }) }));
		~emit.(\anthropic, ~await.({ |done| an.listModels({ |m| done.(\ok) }, { |e| done.(\err, ~errInfo.(e)) }) }));
		~emit.(\remove, ~await.({ |done| store.removeKey(\openai, { done.(\ok) }, { |e| done.(\err, ~errInfo.(e)) }) }));
		~emit.(\removeOther, ~await.({ |done| store.removeKey(\anthropic, { done.(\ok) }, { |e| done.(\err, ~errInfo.(e)) }) }));
		~emit.(\has2, ~await.({ |done| store.hasKey(\openai, done) }));
		~emit.(\afterRemove, ~await.({ |done| oa.listModels({ done.(\ok) }, { |e| done.(\err, ~errInfo.(e)) }) }));
		~emit.(\badKey, ~await.({ |done| store.storeKey(\openai, "bad key with spaces", { done.(\ok) }, { |e| done.(\err, ~errInfo.(e)) }) }));
		""".replace("%PREFIX%", sc_string(self.prefix)).replace(
            "%KEY%", sc_string(FAKE_KEY)).replace("%ANKEY%", sc_string(FAKE_ANTHROPIC_KEY)).replace(
            "%BASE%", sc_string(server.base_url))
        with server:
            run = run_sclang("wincred", body, timeout=120, workdir=self.workdir)
        self.assertEqual(run.get("backend"), ["Windows Credential Manager", self.targets[0]])
        self.assertEqual(run.get("has0"), [False])
        self.assertEqual(run.get("remove0"), ["ok"])
        self.assertEqual(run.get("store"), ["ok"], run.output[-3000:])
        self.assertEqual(run.get("replace"), ["ok"])
        self.assertEqual(run.get("has1"), [True])
        self.assertEqual(run.get("hasOther"), [False])
        self.assertEqual(run.get("validate"), ["ok", 1], run.output[-3000:])
        self.assertEqual(run.get("storeOther"), ["ok"])
        self.assertEqual(run.get("anthropic"), ["ok"])
        self.assertEqual(run.get("remove"), ["ok"])
        self.assertEqual(run.get("removeOther"), ["ok"])
        self.assertEqual(run.get("has2"), [False])
        self.assertEqual(run.get("afterRemove")[1]["kind"], "auth")
        self.assertEqual(run.get("badKey")[1]["kind"], "validation")
        self.assertEqual(len(server.requests), 2)
        self.assertEqual(server.requests[0]["headers"]["authorization"], "Bearer " + FAKE_KEY)
        self.assertEqual(server.requests[1]["headers"]["x-api-key"], FAKE_ANTHROPIC_KEY)
        self.assertNotIn("authorization", server.requests[1]["headers"])
        # The credential really lived in Credential Manager under the test target.
        self.assertTrue(listed and self.targets[0] in listed[0], listed)
        self.assertNotIn(self.targets[0], cmdkey("/list:" + self.targets[0]).stdout)
        self.assertEqual(len(snapshots), 2)
        for snapshot in snapshots:
            self.assertIn("MaxxedBeatsCredential.ps1", snapshot)
            for key in (FAKE_KEY, FAKE_ANTHROPIC_KEY):
                self.assertNotIn(key, snapshot)
        for key in (FAKE_KEY, FAKE_ANTHROPIC_KEY):
            self.assertNotIn(key, run.output)
            self.assertEqual(tree_contains(self.workdir, key), [])


if __name__ == "__main__":
    unittest.main()
