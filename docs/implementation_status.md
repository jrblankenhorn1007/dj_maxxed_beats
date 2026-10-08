# Implementation Status

> Current-state snapshot stored in `docs/implementation_status.md`.
>
> This snapshot is rewritten each iteration; `RALPH_PROGRESS.md` holds
> per-iteration test evidence, and `decision_log.md` is append-only.

## Copilot onboarding — installed Copilot provider verified on macOS

- The precise cause was twofold: the native Copilot CLI was installed
  per-user but outside the `PATH` inherited by SCIDE, and the installed
  extension was stale. Its `Data/copilot` folder contained only `bridge.py`
  and `requirements.txt`, without the new setup helper. The local default
  Python 3.9.6 is also below the SDK's Python 3.11 minimum. Copilot uses
  GitHub browser sign-in, not an API-key field.
- PR #41 added per-user CLI discovery, private SDK runtime setup, persisted
  executable paths, macOS/Linux/Windows setup helpers, a Windows package
  setup flow, and novice launch/sign-in instructions. PR #43 fixed Windows
  test portability, and PR #44 fixed the Ubuntu 22.04 Python/APT fallback.
  The final PR #41 head `e9a003cb537c1cca80f0828b8cf8186d5b49e681` merged
  at `740ccf6cbb7ad875ee1333762dc84b635361cbb1`; all hosted checks and
  round-2 remediation checks passed.
- The dedicated memory review captured reusable runtime-setup and
  platform-testing lessons. PR #45 merged at
  `e73b953671ba72e9af388ceaa21ebcdcfe3d63d6` and is verified on
  `origin/main`.
- Follow-up PR #47 makes the Python/SDK configuration error name the correct
  setup launcher on macOS, Linux, and Windows; it also explains that Git
  authorization does not install the private runtime and Copilot does not use
  an API key. PR #47's exact-head review found no significant issues and its
  hosted checks passed; it merged at
  `edc9c64b138e5e183dc6bea64a8c99cb3253866a`.
- The merged MaxxedBeats and ChaosOsc were reinstalled locally through the
  marker-protected installer; the universal macOS plugin built successfully.
  The setup helper, provider class, and SCIDE launcher are installed. The
  private runtime now has Python 3.14.8, SDK 1.0.16, and official CLI 1.0.93;
  browser sign-in succeeded.
- **Live startup root cause:** the bridge passed the standalone interactive
  CLI and its flags to the SDK's stdio connection. The CLI rejected
  `--deny-tool=*`; after that flag was removed, it still exited without
  completing the SDK handshake. The SDK's own pinned runtime rejected those
  interactive CLI flags as unsupported.
- **Fix merged:** PR #50 replaced the standalone CLI stdio connection with
  the SDK-managed runtime and pre-downloads that runtime during setup using
  the SDK environment's certifi trust bundle. The standalone CLI remains
  responsible only for browser login. Empty tool/MCP lists, a rejecting
  permission handler, and the runtime metadata check keep tools disabled.
  PR #50 merged at `af9828452017d9379f505adcf890342d838d3b7f`.
- **Installed-path verification:** the marker-protected installer replaced
  the default SuperCollider extension from merged `origin/main`. The
  installed bridge SHA-256 matches the merged source. The default installed
  `MBCopilotProvider` reported authenticated status, refreshed 28 models, and
  completed a real `gpt-5-mini` request with the expected
  `MAXXEDBEATS COPILOT CONNECTED.` response.
- **Remaining project acceptance:** the required visible SCIDE scenario on
  Windows 10 x64 and the MacBook Neo has not been run for this latest install.

## Latest loop report

- **Most recently merged implementation iteration:** `10` — Copilot runtime
  error guidance, PR #47 merged at
  `edc9c64b138e5e183dc6bea64a8c99cb3253866a`.
- **Post-merge memory follow-up:** PR #45 merged at
  `e73b953671ba72e9af388ceaa21ebcdcfe3d63d6`. Iteration 10's memory review
  captured an actionable platform-setup error lesson, included with this
  follow-up status update.
- **Current iteration:** branch `ralph/copilot-cli-startup-20261008-0045`,
  based on fetched `origin/main` `1871b5bc9a18951185efa2103dd89e375081007d`.
  PR #50 merged at `af9828452017d9379f505adcf890342d838d3b7f`; the exact-head
  code/security reviews and hosted checks passed. The post-merge memory lesson
  is being integrated in branch `ralph/copilot-sdk-memory-20261008-af98284`.
- **Run state:** `IN_PROGRESS`; the Copilot auth/model/request path now works
  on this Mac. The broader project remains incomplete until the required
  Windows 10 x64 and MacBook Neo visual acceptance is recorded.
- **Current verification:** the focused Copilot bridge/setup suite passed
  **35 tests, 1 skipped**. The full headless gate passed **237 tests,
  7 skipped** in 253.055 seconds. All hosted PR #50 checks passed. The
  installed default provider passed live auth, 28-model refresh, and one
  real short `gpt-5-mini` completion.
- **Runtime setup:** the app's private runtime contains Python 3.14.8, SDK
  1.0.16, and CLI 1.0.93; official browser sign-in is complete. This does not
  replace macOS's system Python. The merged bridge is installed at the default
  extension path. Copilot uses browser sign-in, not an API key.
- **Delivered:** in-SuperCollider assistant window (`MaxxedBeats.gui`),
  OpenAI/Anthropic/mock providers over OS `curl`, OS credential stores,
  model catalog, usage/cost/credits, project review/apply/backup/undo,
  approved separate-process NRT rendering with audio checks, a bounded
  variation loop, GitHub Copilot subscription sign-in, a combined Quark +
  ChaosOsc installer, help, user guide, and an **Assistant Tests** CI workflow
  (macOS and Windows).
- **Windows follow-up (branch `ralph/ai-assistant-windows-20261007`):** the
  Windows transport (curl.exe + PowerShell helper), Windows Credential
  Manager backend, and Windows render launching are implemented. The package
  now requires the Copilot bridge and dependency manifest but still does not
  require Python for the standard provider flows. No assistant behavior tests
  are skipped to hide Windows failures.

## Overall state

The assistant works end to end on macOS with the offline mock provider:
open the window from SCIDE, choose your DJ, propose, review the diff,
confirm the apply (with backup), approve a render that produces a real WAV
with ChaosOsc and checks, undo, and run a variation session with approved
renders and a confirmed apply. Live OpenAI/Anthropic calls are implemented
and tested against loopback fake servers; no billable call has been made.
On Windows the same flows (live-provider transport against loopback fake
servers, Credential Manager, renders, variations, GUI integration) pass the
hosted Assistant Tests suite; no Windows behavior tests are skipped. The zip
package is installed with its `install.ps1`, smoke-tested, and removed in CI.
A physical Windows 10/11 PC and SCIDE-launched visual sign-off remain open
(manual checks). Copilot's SDK auth, live model refresh, and one short request
passed in a fresh SuperCollider provider process on the MacBook Neo through
the new SDK-managed runtime. A subsequent screenshot of the active SCIDE
window reported Copilot unauthenticated and model refresh failing; the
fresh-process result does not establish that this window works. In-app
sign-in/model refresh and a real GUI request still need confirmation. The
Windows visual workflow remains unverified. The official CLI is present
per-user for browser sign-in, while model operations use the runtime pinned by
the SDK.

## Component status

| Area | Status | Current state |
| --- | --- | --- |
| ChaosOsc server plugin | Implemented | `ChaosOsc.ar`/`.kr(chaosAmount, seed, freq, mul, add)`; CMake build for macOS (universal), Linux, Windows (MSVC). |
| SCIDE entry point and window | Implemented | `MaxxedBeats.gui`: project, Choose your DJ (explicit provider/model ids, refresh, stale/unavailable labels, no fallback), conversation, plan (with assumptions/uncertainty/questions), diff review, confirmations, render panel, Play/Reveal, usage, history, variations, keys and privacy notice. [GUI design](./design/gui.md). |
| Providers and transport | Implemented | Direct sclang + OS `curl`; TLS enforced; cancellable; keys never in argv/env/files. Windows: `curl.exe` started by a PowerShell helper that writes the key only to curl's stdin. [Provider design](./design/providers.md). |
| Credentials | Implemented | macOS Keychain via `security` (temporary-keychain test); Windows Credential Manager via the PowerShell helper (real round trip with unique test-only targets); Linux Secret Service command-tested only; in-memory fake for tests. |
| Model catalog | Implemented | Per-provider refresh/cache/selection (`model-catalog.json`, `providers.json`); never substitutes; stale after failure or 24 h. |
| GitHub Copilot | Implemented; active GUI unresolved | Official subscription provider with no API key; setup pre-downloads the SDK-pinned runtime and the official CLI handles browser login. A separate fresh provider process returned 28 models and completed one `gpt-5-mini` request, but the user's active SCIDE screenshot still reports an auth/model-refresh failure. In-window sign-in and a real GUI request remain unverified; tool access remains disabled and Windows GUI behavior is unverified. |
| Usage, USD, credits | Implemented | Versioned rate table `2026-10-06.1`; 100 credits per estimated USD; missing/stale labelled, never zero; local history (`usage-history.json`). |
| Project, proposals, apply, undo | Implemented | Strict `maxxedbeats.proposal/1`; path confinement; confirmed apply with backups; undo refuses after later user edits. [Workflow design](./design/workflow.md). |
| Rendering | Implemented | Approved only; separate `sclang` → Score → `scsynth -N`; POSIX `env -i` + isolated HOME, Windows PowerShell launcher with a cleared environment and `sclang -l` (`excludeDefaultPaths`); installed ChaosOsc in the default plugin paths; checks and JSON sidecar. Linux launching unverified. |
| Variation loop | Implemented | User-started, 1–4 candidates in the GUI (session caps at 16), isolated copies, fixed seeds, renders only with explicit approval, confirmed apply. |
| Mock provider | Implemented | Deterministic `maxxedbeats.proposal/1` replies with a seed-dependent ChaosOsc composition; drives tests and the visual scenario. |
| Packaging | Implemented | `scripts/install_maxxedbeats.py` installs/removes the Quark (with `agent/*.md`) and ChaosOsc together; marker-protected; dry run. Windows without developer tools: `MaxxedBeats-Windows-x64.zip` includes the Copilot bridge/requirements and documents its optional Python/CLI prerequisites; hosted install/smoke/uninstall passed. |
| Documentation | Implemented | [User guide](./USER_GUIDE.md), README, SCDoc help, three design docs. |
| Tests and CI | Implemented | PR #50 passes Assistant Tests (macOS/Windows), Windows package, Headless Tests, and Plugin Builds (three OSes). The startup fix passes the full headless gate (237 tests, 7 skips); the installed Copilot provider passes live auth/model refresh and one short request on the MacBook Neo. |
| Visual verification | Partial; active GUI auth unresolved | The installed extension's class library compiled in headless sclang and a separate fresh provider process passed, but the user's screenshot of the active SCIDE shows Copilot unauthenticated and model refresh failing. No successful SCIDE walkthrough/request has been verified. Required SCIDE-launched sign-off on Windows 10 x64 and MacBook Neo remains open. |

## Verification and platform coverage

- **MacBook Neo** (`Mac17,5`, macOS 26, SuperCollider 3.14.1): full headless
  gate, GUI integration with real NRT renders, Keychain round trip in a
  temporary keychain, and screenshot capture. See `RALPH_PROGRESS.md`
  (iterations 7-8) for commands and counts.
- **Windows:** CI only: PR #37 Assistant Tests pass on `windows-latest` and run
  all assistant behavior suites; the sole skip is the macOS Keychain test.
  The workflow also installs/smoke-tests/uninstalls the zip package; Plugin
  Builds renders an NRT smoke test. No physical Windows 10/11 run.
- **Linux:** plugin build and installer in CI; assistant untested.

## Blockers and risks

- A physical Windows 10/11 PC is still unverified, including sound and window
  appearance.
- The SCIDE-launched visual scenario remains open on the MacBook Neo and
  Windows 10 x64. The headless live Copilot validation does not replace it.
- No live OpenAI/Anthropic request has been made (by design; requires the
  owner's key and consent).
- Prices change; the rate table must be refreshed (it labels itself stale
  after 45 days).

## Open questions and next task

- SCIDE-launched visual sign-off on the MacBook Neo and on a physical
  Windows 10/11 PC with the zip package (`VISUAL_TEST_PLAN.md`).
- Run the SCIDE-launched visual workflow with the deterministic mock provider
  on the MacBook Neo and physical Windows 10 x64.
- Owner-run live smoke test with a real API key and a spending limit; live
  OpenAI/Anthropic requests remain opt-in.
