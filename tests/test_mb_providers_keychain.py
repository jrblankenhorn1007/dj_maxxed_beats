"""macOS Keychain backend round trip using a temporary keychain file only.

The login keychain and the user's keychain search list are never touched:
the store is pointed at an explicit keychain path under tests/.build, and the
test verifies the user search list is unchanged afterwards.
"""

import shutil
import subprocess
import sys
import unittest

from mb_providers.fake_server import FakeProviderServer
from mb_providers.harness import (
    FAKE_KEY, fresh_workdir, isolated_env, run_sclang, sc_string, tree_contains,
)


@unittest.skipUnless(sys.platform == "darwin" and shutil.which("security"),
                     "macOS security CLI required")
class KeychainBackendTests(unittest.TestCase):
    def setUp(self):
        self.workdir = fresh_workdir("keychain")
        self.env, _ = isolated_env(self.workdir)
        self.keychain = self.workdir / "mb-test.keychain-db"
        self.search_list = self.user_search_list()
        subprocess.run(["security", "create-keychain", "-p", "mb-test-only", str(self.keychain)],
                       env=self.env, check=True, capture_output=True)
        subprocess.run(["security", "set-keychain-settings", str(self.keychain)],
                       env=self.env, check=True, capture_output=True)

    def tearDown(self):
        subprocess.run(["security", "delete-keychain", str(self.keychain)],
                       env=self.env, capture_output=True)
        self.assertEqual(self.user_search_list(), self.search_list)

    @staticmethod
    def user_search_list():
        return subprocess.run(["security", "list-keychains", "-d", "user"],
                              capture_output=True, text=True).stdout

    def test_store_use_validate_and_remove_key_in_temporary_keychain(self):
        server = FakeProviderServer()
        server.route("GET", "/v1/models", {"status": 200, "body": {"data": [{"id": "gpt-5"}]}})
        body = r"""
		var store = MBKeychainCredentialStore.new(%KC%), oa, r;
		oa = MBOpenAIProvider.new(store, %BASE%, 10);
		~emit.(\has0, ~await.({ |done| store.hasKey(\openai, done) }));
		~emit.(\store, ~await.({ |done| store.storeKey(\openai, %KEY%, { done.(\ok) }, { |e| done.(\err, ~errInfo.(e)) }) }));
		~emit.(\replace, ~await.({ |done| store.storeKey(\openai, %KEY%, { done.(\ok) }, { |e| done.(\err, ~errInfo.(e)) }) }));
		~emit.(\has1, ~await.({ |done| store.hasKey(\openai, done) }));
		~emit.(\hasOther, ~await.({ |done| store.hasKey(\anthropic, done) }));
		~emit.(\validate, ~await.({ |done| store.validateKey(\openai, { |m| done.(\ok, m.size) }, { |e| done.(\err, ~errInfo.(e)) }, oa) }));
		~emit.(\remove, ~await.({ |done| store.removeKey(\openai, { done.(\ok) }, { |e| done.(\err, ~errInfo.(e)) }) }));
		~emit.(\has2, ~await.({ |done| store.hasKey(\openai, done) }));
		~emit.(\afterRemove, ~await.({ |done| oa.listModels({ done.(\ok) }, { |e| done.(\err, ~errInfo.(e)) }) }));
		""".replace("%KC%", sc_string(str(self.keychain))).replace(
            "%KEY%", sc_string(FAKE_KEY)).replace("%BASE%", sc_string(server.base_url))
        with server:
            run = run_sclang("keychain", body, workdir=self.workdir)
        self.assertEqual(run.get("has0"), [False])
        self.assertEqual(run.get("store"), ["ok"])
        self.assertEqual(run.get("replace"), ["ok"])
        self.assertEqual(run.get("has1"), [True])
        self.assertEqual(run.get("hasOther"), [False])
        self.assertEqual(run.get("validate"), ["ok", 1])
        self.assertEqual(run.get("remove"), ["ok"])
        self.assertEqual(run.get("has2"), [False])
        self.assertEqual(run.get("afterRemove")[1]["kind"], "auth")
        self.assertEqual(server.requests[0]["headers"]["authorization"], "Bearer " + FAKE_KEY)
        self.assertEqual(len(server.requests), 1)
        self.assertNotIn(FAKE_KEY, run.output)
        hits = [p for p in tree_contains(self.workdir, FAKE_KEY)
                if not p.startswith(str(self.keychain))]
        self.assertEqual(hits, [])


if __name__ == "__main__":
    unittest.main()
