# Ralph Progress — Copilot auth-home fix

## Iteration 4 — Preserve the user's Copilot authentication home

- **Run/task:** `copilot-setup-onboarding-20261007-1640` /
  `copilot-runtime-setup-onboarding`.
- **Branch/worktree:** `ralph/copilot-auth-path-fix-20261008-288416a` /
  `/Users/jrblankenhorn/dj_maxxed_beats.worktrees/ralph-copilot-auth-path-fix-20261008-288416a`.
- **Base:** `origin/main` at
  `288416aa955a270cf0167593bbe54005743c6b81`.
- **Root cause:** passing the per-request temporary directory as
  `CopilotClient.base_directory` made the SDK look for auth under a temporary
  `COPILOT_HOME`, not the user's saved `~/.copilot` login. The new SCIDE
  process already had Python 3.14.8, SDK 1.0.16, and the CLI; this was not a
  stale Python installation or missing API key.
- **Red:** before production changes,
  `PYTHONPATH=tests python3 -m unittest -v
  test_mb_copilot.CopilotBridgeTests.test_sdk_startup_uses_sdk_runtime_without_relaxing_tool_denial`
  failed because the SDK factory received `base_directory=<per-request path>`.
- **Green:** `sdk_client` no longer passes `base_directory`. The SDK therefore
  uses its stable default user auth home. Per-request `working_directory` and
  `config_dir` remain set by the SDK session, and tool/MCP denial is unchanged.
- **Focused regression:** the named test passed with the private Python 3.14.8
  runtime. `SCLANG=... SCSYNTH=... PYTHONPATH=tests python3 -m unittest
  test_mb_copilot test_mb_copilot_setup -q` passed **35 tests, 1 skipped**.
- **Runner note:** the same focused suite initially ran with the private SDK
  Python and failed the existing missing-runtime fixture (`network` instead
  of `config`), because that interpreter has the SDK installed. The documented
  repository `python3` command passed; no test was weakened.
- **Live auth probe:** ran the branch bridge against the actual app run
  directory with `PATH=/usr/bin:/bin:/usr/sbin:/sbin` and the user's saved
  login. Response: `{"authenticated": true}`. The old bridge returned false
  under the same environment.
- **Full gate:** the repository `scripts/run_headless_tests.sh` passed
  **237 tests, 7 skipped** in **242.434 seconds** with the app Python's
  certifi bundle. `git diff --check` passed.
- **Remaining acceptance:** the branch code is not yet installed into the
  active SCIDE extension. In-window model refresh, a real GUI request, and
  physical Windows 10 x64 visual acceptance remain unverified.
- **Next:** after iteration 5 and its memory review are merged, install the
  final bridge and verify auth, model refresh, and one short request inside
  the active SCIDE window. Keep the overall run `IN_PROGRESS`.

## PR #53 merge synchronization

- **Merged:** PR #53 merged at `2026-10-08T03:20:54Z` as
  `3515844e4db4b7a6a58a2d1ed1a49b9e518cc8a5`; after fetching,
  `git merge-base --is-ancestor` verified the merge on `origin/main`.
- **Review/checks:** both exact-head reviewers found no issue in the PR diff;
  all hosted Assistant, headless, Windows package, and Plugin Builds checks
  passed. The code reviewer separately identified the telemetry-config bug
  documented in iteration 5.
- **Still open:** the PR #53 bridge fix is not installed in the active SCIDE
  extension. Its authentication/model refresh and a real GUI request remain
  unverified; physical Windows 10 x64 visual acceptance is also open.
