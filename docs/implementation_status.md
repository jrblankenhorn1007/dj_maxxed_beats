# Implementation Status

> Current-state snapshot stored in `docs/implementation_status.md`.
>
> This snapshot is rewritten each iteration; `RALPH_PROGRESS.md` holds
> per-iteration test evidence, and `decision_log.md` is append-only.

## Onboarding follow-up in progress

- Branch `ralph/copilot-windows-onboarding-20261007-1640` is addressing the
  Copilot runtime setup gap: the native CLI was installed per-user but absent
  from SCIDE's `PATH`, and the local default Python 3.9.6 is below the SDK's
  Python 3.11 minimum. The existing Copilot provider uses browser sign-in,
  not an API-key field.
- The branch adds private runtime setup, live config refresh, platform
  launchers, one-click Windows package wrappers, and install/launch/sign-in
  instructions. Round-1 review findings were fixed by pinning and verifying
  the macOS/Linux Copilot CLI release, accepting Python 3.14/generic `python3`,
  and requiring an interactive Linux terminal. The local full gate passes 232
  tests with five platform/opt-in skips, and the pinned CLI download/checksum
  was verified locally. Implementation commit
  `cab1f464346953e6a39b4477125de0c8bcc6a078` is committed locally. Hosted
  Windows/macOS checks passed on PR #41's updated head `f8f400a`, including the
  replacement review-fix PR. Round-2 security review found no vulnerabilities;
  code review's Ubuntu 22.04 APT/Python fallback finding is fixed locally and
  needs a stacked PR, hosted rerun, and targeted remediation confirmation.
  Live sign-in/generation has not been tested; the branch is not merged.

## Latest loop report

- **Most recently merged implementation iteration:** `8` — Windows CI fixes
  and the requested GitHub Copilot provider; PR #37 merged to `origin/main` at
  `66aac98e566f3ecb25d893d726e9568e8c65f6bf`.
- **Implementation commit:** `822db890bef35da1e559634af4ddc0f418afa60d`.
- **Post-merge memory/status follow-up:** PR #38 merged to `origin/main` at
  `36ba6c3e5d3e7dea06aa711608804b1ab56a4e76`; the categorized cross-platform
  lessons and coordinator run progress are integrated. This is part of
  iteration 8, not a new implementation iteration.
- **Coordinator sign-out:** recorded in coordinator status revision 3; this
  final status update is awaiting integration.
- **Loop state:** implementation content and memory update are merged and
  verified; the coordinator run remains in progress until this status update
  is merged and its merge SHA is verified on `origin/main`.
- **Current verification:** the full local gate passes **213 tests** with four
  existing platform/opt-in skips. PR run `37653854390` passed the Windows
  assistant suite (105 tests; only the macOS Keychain test skipped), macOS
  suite, and Windows package install/smoke/uninstall. Headless Tests
  `37653854360` and all three Plugin Builds jobs in `37653854372` passed.
  PR #38 passed all 14 hosted checks, received a `CLEAN` independent review,
  and its merge was verified on fetched `origin/main`.
  Copilot sign-in appears in the shared Keys & Privacy provider rows and is
  covered by GUI/factory tests.
- **User installation:** the actual assistant is installed and its native
  window is open on the Mac. It uses installed classes, not test fake services.
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
(manual checks). Copilot's bridge and SDK behavior are tested with fakes; live
CLI sign-in/generation are not verified because Python 3.11 and the Copilot
CLI are not installed here.

## Component status

| Area | Status | Current state |
| --- | --- | --- |
| ChaosOsc server plugin | Implemented | `ChaosOsc.ar`/`.kr(chaosAmount, seed, freq, mul, add)`; CMake build for macOS (universal), Linux, Windows (MSVC). |
| SCIDE entry point and window | Implemented | `MaxxedBeats.gui`: project, Choose your DJ (explicit provider/model ids, refresh, stale/unavailable labels, no fallback), conversation, plan (with assumptions/uncertainty/questions), diff review, confirmations, render panel, Play/Reveal, usage, history, variations, keys and privacy notice. [GUI design](./design/gui.md). |
| Providers and transport | Implemented | Direct sclang + OS `curl`; TLS enforced; cancellable; keys never in argv/env/files. Windows: `curl.exe` started by a PowerShell helper that writes the key only to curl's stdin. [Provider design](./design/providers.md). |
| Credentials | Implemented | macOS Keychain via `security` (temporary-keychain test); Windows Credential Manager via the PowerShell helper (real round trip with unique test-only targets); Linux Secret Service command-tested only; in-memory fake for tests. |
| Model catalog | Implemented | Per-provider refresh/cache/selection (`model-catalog.json`, `providers.json`); never substitutes; stale after failure or 24 h. |
| GitHub Copilot | Implemented; live runtime unverified | Official runtime-backed subscription provider, no API key, dynamic model discovery, tools disabled; sign-in is in the shared credential-row group and package files are required. GUI/factory tests pass. Live CLI sign-in/generation remain unverified. |
| Usage, USD, credits | Implemented | Versioned rate table `2026-10-06.1`; 100 credits per estimated USD; missing/stale labelled, never zero; local history (`usage-history.json`). |
| Project, proposals, apply, undo | Implemented | Strict `maxxedbeats.proposal/1`; path confinement; confirmed apply with backups; undo refuses after later user edits. [Workflow design](./design/workflow.md). |
| Rendering | Implemented | Approved only; separate `sclang` → Score → `scsynth -N`; POSIX `env -i` + isolated HOME, Windows PowerShell launcher with a cleared environment and `sclang -l` (`excludeDefaultPaths`); installed ChaosOsc in the default plugin paths; checks and JSON sidecar. Linux launching unverified. |
| Variation loop | Implemented | User-started, 1–4 candidates in the GUI (session caps at 16), isolated copies, fixed seeds, renders only with explicit approval, confirmed apply. |
| Mock provider | Implemented | Deterministic `maxxedbeats.proposal/1` replies with a seed-dependent ChaosOsc composition; drives tests and the visual scenario. |
| Packaging | Implemented | `scripts/install_maxxedbeats.py` installs/removes the Quark (with `agent/*.md`) and ChaosOsc together; marker-protected; dry run. Windows without developer tools: `MaxxedBeats-Windows-x64.zip` includes the Copilot bridge/requirements and documents its optional Python/CLI prerequisites; hosted install/smoke/uninstall passed. |
| Documentation | Implemented | [User guide](./USER_GUIDE.md), README, SCDoc help, three design docs. |
| Tests and CI | Implemented | Full local gate: 213 tests, four existing platform/opt-in skips. PR #37 passes **Assistant Tests** (macOS 14 + Windows), **Headless Tests** (macOS 14), and **Plugin Builds** (three OSes). Header downloads retry with backoff and are cached in CI. |
| Visual verification | Partial | Captured and inspected the native Keys & Privacy page; Copilot appears as a peer row beside OpenAI and Anthropic. SCIDE-launched sign-off and physical Windows visual check remain open. |

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
- No live OpenAI/Anthropic request has been made (by design; requires the
  owner's key and consent).
- Prices change; the rate table must be refreshed (it labels itself stale
  after 45 days).

## Open questions and next task

- SCIDE-launched visual sign-off on the MacBook Neo and on a physical
  Windows 10/11 PC with the zip package (`VISUAL_TEST_PLAN.md`).
- Merge and verify the post-merge memory update, then merge the final
  coordinator sign-out status record.
- Owner-run live smoke test with a real API key and a spending limit; live
  Copilot sign-in/generation also needs the optional Python 3.11+/CLI setup.
