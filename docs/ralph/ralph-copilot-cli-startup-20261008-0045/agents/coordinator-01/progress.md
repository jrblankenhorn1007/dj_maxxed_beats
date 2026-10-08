# Copilot SDK runtime startup progress

## Iteration 3 — live Copilot runtime and provider verification

- **Run/task:** `copilot-setup-onboarding-20261007-1640` /
  `copilot-runtime-setup-onboarding`.
- **Coordinator:** `coordinator-01 / Copilot runtime startup fix`.
- **Branch/worktree:** `ralph/copilot-cli-startup-20261008-0045` /
  `/Users/jrblankenhorn/dj_maxxed_beats.worktrees/ralph-copilot-cli-startup-20261008-0045`.
- **Base:** fetched `origin/main` at
  `1871b5bc9a18951185efa2103dd89e375081007d`.
- **Implementation commit:** `68708847c72d601f1f997589f2d5011a8deb65a6`.
- **Scope:** start the Copilot SDK runtime correctly, preserve the no-tools
  boundary, pre-provision the compatible runtime in setup, and verify live
  authentication, model discovery, and a minimal completion.
- **Root cause:** the bridge passed the ordinary interactive Copilot CLI
  (1.0.93) and CLI-specific flags to `StdioRuntimeConnection`. That executable
  is used for browser login; SDK 1.0.16 provisions its own pinned stdio runtime.
  The standalone CLI rejected `--deny-tool=*`, then exited before the SDK
  handshake even after that flag was removed. The SDK runtime rejected
  `--disable-builtin-mcps` as an unsupported argument.
- **Red — runtime connection:** before production changes,
  `PYTHONPATH=tests python3 -m unittest -v
  test_mb_copilot.CopilotBridgeTests.test_sdk_startup_uses_sdk_runtime_without_relaxing_tool_denial`
  failed because `sdk_client` passed `path='native-copilot'` and CLI-only
  arguments instead of constructing the SDK's default stdio connection.
- **Red — setup:** before production changes,
  `PYTHONPATH=tests python3 -m unittest -v
  test_mb_copilot_setup.CopilotSetupTests.test_setup_installs_pinned_sdk_and_saves_runtime_paths`
  failed because setup did not provision the SDK-compatible runtime.
- **Green:** model operations now use `StdioRuntimeConnection()` with no
  standalone CLI path or flags. The SDK session still exposes no tools or MCP
  servers, rejects permission requests, and refuses generation if runtime
  tool metadata is non-empty. Setup uses the SDK's official
  `download-runtime` entry point and `certifi.where()` before saving runtime
  configuration.
- **Focused check:**
  `SCLANG=/Applications/SuperCollider.app/Contents/MacOS/sclang
  SCSYNTH=/Applications/SuperCollider.app/Contents/Resources/scsynth
  PYTHONPATH=tests python3 -m unittest test_mb_copilot test_mb_copilot_setup -q`
  passed **35 tests, 1 skipped**.
- **Final targeted/refactor verification:** the same focused command passed
  after the final implementation. No separate behavior-changing refactor was
  needed.
- **Live backend verification:** using the installed private Python 3.14.8
  runtime, SDK 1.0.16, and the user's official browser login, the branch bridge
  returned authenticated status and 28 models. One `gpt-5-mini` completion
  returned `MAXXEDBEATS COPILOT CONNECTED.` The bridge verified that no tools
  were exposed before sending that request.
- **Live SuperCollider provider verification:** `MBCopilotProvider.authStatus`
  and `MBCopilotProvider.listModels` callbacks, using the installed class and
  the branch bridge, returned authenticated status and 28 models. The first
  headless probe loaded the same classes from both the installed extension
  and source worktree; rerunning with the installed class tree and isolated
  XDG config removed the duplicate-class setup issue. A probe with an isolated
  HOME could not see the user's login; preserving the real HOME while
  isolating class discovery passed.
- **Recovered TLS setup issue:** the SDK downloader and the first full-gate
  attempt failed with Python's `CERTIFICATE_VERIFY_FAILED` because the
  Python.org Python 3.14 install did not have a default CA bundle configured.
  Pointing `SSL_CERT_FILE` to the SDK environment's `certifi` bundle
  downloaded the runtime successfully and allowed the full gate to complete.
  Setup now applies that certifi bundle when pre-downloading the SDK runtime.
- **Required project gate:**
  `PYTHONDONTWRITEBYTECODE=1
  SSL_CERT_FILE='/Users/jrblankenhorn/Library/Application Support/MaxxedBeats/Copilot/venv/lib/python3.14/site-packages/certifi/cacert.pem'
  SCLANG=/Applications/SuperCollider.app/Contents/MacOS/sclang
  SCSYNTH=/Applications/SuperCollider.app/Contents/Resources/scsynth
  bash scripts/run_headless_tests.sh`
  passed **237 tests, 7 skipped** in 253.055 seconds.
- **Remaining coverage:** no SCIDE visual scenario was performed in this
  iteration; physical Windows 10 x64 visual acceptance remains open.
- **Exact-head review:** PR #50 base/head were
  `1871b5bc9a18951185efa2103dd89e375081007d` /
  `00b2e80ae1aaae5338de97515d2a4cc5d721f5c5`. The code reviewer reported no
  significant issues; the security reviewer reported no vulnerabilities.
- **Hosted checks:** `gh pr checks 50` passed all Assistant macOS/Windows,
  headless, Windows package, and macOS/Linux/Windows plugin-build checks.
- **Merge:** `gh pr merge 50 --merge` returned success at
  `2026-10-08T01:29:43Z`; merge SHA
  `af9828452017d9379f505adcf890342d838d3b7f`. After `git fetch origin`,
  `git merge-base --is-ancestor af9828452017d9379f505adcf890342d838d3b7f origin/main`
  passed.
- **Installed default path:** the merged source was installed with
  `python3 scripts/install_maxxedbeats.py --dry-run` followed by
  `python3 scripts/install_maxxedbeats.py`. Source and installed bridge
  SHA-256 matched. The installed `MBCopilotProvider` returned authenticated
  status, 28 models, and one real `gpt-5-mini` response:
  `MAXXEDBEATS COPILOT CONNECTED.`
- **Memory review:** the Project Memory skill and `.github/memory/README.md`,
  `runtime-setup.md`, and `git-workflow.md` were reviewed. No duplicate
  SDK-managed-runtime lesson existed; the new durable lesson is being
  integrated on `ralph/copilot-sdk-memory-20261008-af98284`.
- **Remaining:** the memory follow-up merge and final run-status sync remain
  pending. SCIDE visual acceptance and physical Windows 10 x64 visual
  acceptance remain outside this iteration.
