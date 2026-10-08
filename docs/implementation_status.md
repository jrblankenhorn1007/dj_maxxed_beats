# Implementation Status

> Current-state snapshot stored in `docs/implementation_status.md`.
>
> This snapshot is rewritten each iteration; `RALPH_PROGRESS.md` holds
> per-iteration test evidence, and `decision_log.md` is append-only.

## Copilot onboarding — active SCIDE acceptance pending

- The initial setup gap (per-user CLI outside SCIDE's inherited `PATH`,
  stale extension contents, and system-default Python 3.9.6 below the SDK's
  minimum) was addressed by the setup/runtime work below. The app-private
  Copilot environment is Python 3.14.8 with SDK 1.0.16 and CLI 1.0.93; the
  system Python was not changed. The later active-SCIDE authentication
  failure had a separate cause, fixed by PR #53 below. Copilot uses GitHub
  browser sign-in, not an API-key field.
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
- **Active-SCIDE auth correction:** PR #53 fixed the bridge's temporary
  `COPILOT_HOME` override and merged at
  `3515844e4db4b7a6a58a2d1ed1a49b9e518cc8a5`. That fix is not yet installed
  in the active extension; the earlier installed-path success was the
  separate PR #50 provider-process test and does not prove the active SCIDE
  window works.
- **Privacy follow-up:** iteration 13 found that the bridge's
  `telemetry={"enabled": false}` still enables OpenTelemetry in SDK 1.0.16.
  The local fix omits the telemetry option and strips inherited
  `COPILOT_*`/`OTEL_*` variables; focused and full headless tests pass. The
  candidate is not yet published or merged.
- **Remaining project acceptance:** the required visible SCIDE scenario on
  Windows 10 x64 and the MacBook Neo has not been run for this latest install.

## Latest loop report

- **Most recently merged authentication fix:** iteration `12`, PR #53, merge
  `3515844e4db4b7a6a58a2d1ed1a49b9e518cc8a5`. It removes the per-request
  `CopilotClient.base_directory` override so the SDK uses the user's saved
  auth home. Exact-head code/security reviews and hosted checks passed.
- **Current iteration:** `13`, branch
  `ralph/copilot-telemetry-hardening-20261008-3515844-ci1`, based on
  `3515844e4db4b7a6a58a2d1ed1a49b9e518cc8a5`, implementation commit
  `9b936df7b4787e2d3bb02ab60ee2eaa50216a704`. SDK 1.0.16 treats every
  non-null telemetry configuration as enabled, even `enabled:false`; the
  candidate omits that option and filters inherited `COPILOT_*` and `OTEL_*`
  environment variables. It is not yet published, reviewed, or merged.
- **Run state:** `IN_PROGRESS`. The active SCIDE window has not been
  re-tested since PR #53 merged because its installed bridge has not been
  replaced. In-window authentication, model refresh, and a real GUI request
  are still unverified. Do not treat the prior separate-process request as
  active-window acceptance.
- **Current verification:** iteration 13 Red confirmed both telemetry
  regressions; Green passed **36 focused tests, 1 skipped** and the full
  headless gate (**238 tests, 7 skipped**, 343.896 seconds). Its auth-only
  bridge probe returned `{"authenticated": true}` with SCIDE's minimal
  `PATH`; it did not generate a completion.
- **Runtime setup:** the app-private environment has Python 3.14.8, SDK
  1.0.16, and CLI 1.0.93. The user's browser sign-in is present. System Python
  remains 3.9.6; it is not the runtime used by the Copilot bridge.
- **Next:** complete the iteration 13 PR/review/merge and required memory
  review; install the resulting merged bridge into the active extension;
  verify authentication and model refresh in that SCIDE window; then send
  one short, user-authorized real request.
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
(manual checks). The PR #50 SDK-managed runtime previously passed auth, model
refresh, and one short request in a fresh provider process, but that did not
resolve the active SCIDE window's reported authentication failure. PR #53 now
fixes the root cause, but its bridge has not yet been installed into that
window. The local auth probe confirms the branch bridge can see the saved
login; in-window authentication/model refresh and a real GUI request remain
unverified. The Windows visual workflow remains unverified. The official CLI
is present per-user for browser sign-in, while model operations use the
runtime pinned by the SDK.

## Component status

| Area | Status | Current state |
| --- | --- | --- |
| ChaosOsc server plugin | Implemented | `ChaosOsc.ar`/`.kr(chaosAmount, seed, freq, mul, add)`; CMake build for macOS (universal), Linux, Windows (MSVC). |
| SCIDE entry point and window | Implemented | `MaxxedBeats.gui`: project, Choose your DJ (explicit provider/model ids, refresh, stale/unavailable labels, no fallback), conversation, plan (with assumptions/uncertainty/questions), diff review, confirmations, render panel, Play/Reveal, usage, history, variations, keys and privacy notice. [GUI design](./design/gui.md). |
| Providers and transport | Implemented | Direct sclang + OS `curl`; TLS enforced; cancellable; keys never in argv/env/files. Windows: `curl.exe` started by a PowerShell helper that writes the key only to curl's stdin. [Provider design](./design/providers.md). |
| Credentials | Implemented | macOS Keychain via `security` (temporary-keychain test); Windows Credential Manager via the PowerShell helper (real round trip with unique test-only targets); Linux Secret Service command-tested only; in-memory fake for tests. |
| Model catalog | Implemented | Per-provider refresh/cache/selection (`model-catalog.json`, `providers.json`); never substitutes; stale after failure or 24 h. |
| GitHub Copilot | Auth fix merged; active GUI unverified | Official subscription provider with no API key. PR #53 corrects the auth-home root cause but is not installed in the active SCIDE extension yet. Iteration 13's telemetry/privacy fix passes local tests but is not merged. Branch auth probe succeeds; in-window sign-in/model refresh and a real GUI request remain unverified. Tool access remains disabled; Windows GUI behavior is unverified. |
| Usage, USD, credits | Implemented | Versioned rate table `2026-10-06.1`; 100 credits per estimated USD; missing/stale labelled, never zero; local history (`usage-history.json`). |
| Project, proposals, apply, undo | Implemented | Strict `maxxedbeats.proposal/1`; path confinement; confirmed apply with backups; undo refuses after later user edits. [Workflow design](./design/workflow.md). |
| Rendering | Implemented | Approved only; separate `sclang` → Score → `scsynth -N`; POSIX `env -i` + isolated HOME, Windows PowerShell launcher with a cleared environment and `sclang -l` (`excludeDefaultPaths`); installed ChaosOsc in the default plugin paths; checks and JSON sidecar. Linux launching unverified. |
| Variation loop | Implemented | User-started, 1–4 candidates in the GUI (session caps at 16), isolated copies, fixed seeds, renders only with explicit approval, confirmed apply. |
| Mock provider | Implemented | Deterministic `maxxedbeats.proposal/1` replies with a seed-dependent ChaosOsc composition; drives tests and the visual scenario. |
| Packaging | Implemented | `scripts/install_maxxedbeats.py` installs/removes the Quark (with `agent/*.md`) and ChaosOsc together; marker-protected; dry run. Windows without developer tools: `MaxxedBeats-Windows-x64.zip` includes the Copilot bridge/requirements and documents its optional Python/CLI prerequisites; hosted install/smoke/uninstall passed. |
| Documentation | Implemented | [User guide](./USER_GUIDE.md), README, SCDoc help, three design docs. |
| Tests and CI | Implemented; iteration 13 PR pending | PR #53 hosted checks passed. Iteration 13 telemetry regression tests and full headless gate pass locally (238 tests, 7 skips); hosted checks/review/merge are pending. The earlier PR #50 provider-process request does not prove the current active SCIDE window works. |
| Visual verification | Partial; active GUI acceptance pending | PR #53 fixes the reported auth-home cause but its bridge has not been installed into the active SCIDE window. No successful in-window authentication/model refresh/request has been verified after that fix. Required SCIDE-launched sign-off on Windows 10 x64 and MacBook Neo remains open. |

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
