# Implementation Status

> Current-state snapshot stored in `docs/implementation_status.md`.
>
> This snapshot is rewritten each iteration; `RALPH_PROGRESS.md` holds
> per-iteration test evidence, and `decision_log.md` is append-only.

## Copilot onboarding — implementation merged, local install refreshed

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
- The merged MaxxedBeats and ChaosOsc were reinstalled locally through the
  marker-protected installer; the universal macOS plugin built successfully.
  The installed setup helper, bridge, provider class, and SCIDE launcher match
  `origin/main`. A focused post-install run passed 32 Copilot tests with one
  Windows-only skip.
- **Current state: BLOCKED on manual runtime/authentication and visual
  acceptance.** Python 3.11+ is not present here and Homebrew is unavailable;
  the setup helper opens the official Python download page. After installing
  Python 3.11+, the user must rerun setup and complete GitHub's browser
  sign-in. Live sign-in/generation was not tested. The required Windows 10
  x64 and MacBook Neo visual scenario also remains open.

## Latest loop report

- **Most recently merged implementation iteration:** `9` — Copilot runtime
  onboarding and Windows package, PR #41 merged at
  `740ccf6cbb7ad875ee1333762dc84b635361cbb1`.
- **Post-merge memory follow-up:** PR #45 merged at
  `e73b953671ba72e9af388ceaa21ebcdcfe3d63d6`; the categorized lessons are
  integrated and verified on fetched `origin/main`.
- **Run state:** `BLOCKED` pending the user's one-time Python 3.11+ setup and
  GitHub browser sign-in, plus the required Windows 10 x64 and MacBook Neo
  visual acceptance. No project-wide `RALPH_COMPLETE` is claimed.
- **Current verification:** hosted Assistant (macOS/Windows), Windows package,
  headless, and three-platform ChaosOsc checks passed on the final PR #41
  head. The post-install local Copilot test run passed **32 tests** with one
  Windows-only skip; the local installer built and installed universal
  macOS ChaosOsc.
- **User installation:** the stale default Extensions copy was replaced by
  the merged build. The setup helper is present and executable; SCIDE has not
  been recompiled or visually retested in this session.
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
CLI setup/sign-in/generation are not verified because Python 3.11+ is not
installed here. The official CLI is present per-user; the merged setup helper
is now installed and directs the user to Python.org for the required runtime.

## Component status

| Area | Status | Current state |
| --- | --- | --- |
| ChaosOsc server plugin | Implemented | `ChaosOsc.ar`/`.kr(chaosAmount, seed, freq, mul, add)`; CMake build for macOS (universal), Linux, Windows (MSVC). |
| SCIDE entry point and window | Implemented | `MaxxedBeats.gui`: project, Choose your DJ (explicit provider/model ids, refresh, stale/unavailable labels, no fallback), conversation, plan (with assumptions/uncertainty/questions), diff review, confirmations, render panel, Play/Reveal, usage, history, variations, keys and privacy notice. [GUI design](./design/gui.md). |
| Providers and transport | Implemented | Direct sclang + OS `curl`; TLS enforced; cancellable; keys never in argv/env/files. Windows: `curl.exe` started by a PowerShell helper that writes the key only to curl's stdin. [Provider design](./design/providers.md). |
| Credentials | Implemented | macOS Keychain via `security` (temporary-keychain test); Windows Credential Manager via the PowerShell helper (real round trip with unique test-only targets); Linux Secret Service command-tested only; in-memory fake for tests. |
| Model catalog | Implemented | Per-provider refresh/cache/selection (`model-catalog.json`, `providers.json`); never substitutes; stale after failure or 24 h. |
| GitHub Copilot | Implemented; live runtime unverified | Official runtime-backed subscription provider, no API key, dynamic model discovery, tools disabled; setup helper and saved-path refresh are installed. GUI/factory tests pass. Python 3.11+ setup and live CLI sign-in/generation remain unverified. |
| Usage, USD, credits | Implemented | Versioned rate table `2026-10-06.1`; 100 credits per estimated USD; missing/stale labelled, never zero; local history (`usage-history.json`). |
| Project, proposals, apply, undo | Implemented | Strict `maxxedbeats.proposal/1`; path confinement; confirmed apply with backups; undo refuses after later user edits. [Workflow design](./design/workflow.md). |
| Rendering | Implemented | Approved only; separate `sclang` → Score → `scsynth -N`; POSIX `env -i` + isolated HOME, Windows PowerShell launcher with a cleared environment and `sclang -l` (`excludeDefaultPaths`); installed ChaosOsc in the default plugin paths; checks and JSON sidecar. Linux launching unverified. |
| Variation loop | Implemented | User-started, 1–4 candidates in the GUI (session caps at 16), isolated copies, fixed seeds, renders only with explicit approval, confirmed apply. |
| Mock provider | Implemented | Deterministic `maxxedbeats.proposal/1` replies with a seed-dependent ChaosOsc composition; drives tests and the visual scenario. |
| Packaging | Implemented | `scripts/install_maxxedbeats.py` installs/removes the Quark (with `agent/*.md`) and ChaosOsc together; marker-protected; dry run. Windows without developer tools: `MaxxedBeats-Windows-x64.zip` includes the Copilot bridge/requirements and documents its optional Python/CLI prerequisites; hosted install/smoke/uninstall passed. |
| Documentation | Implemented | [User guide](./USER_GUIDE.md), README, SCDoc help, three design docs. |
| Tests and CI | Implemented | The full local gate before the final Ubuntu fallback follow-up passed 232 tests with five platform/opt-in skips. PR #41 final head passes Assistant Tests (macOS/Windows), Windows package, Headless Tests, and Plugin Builds (three OSes). Post-install focused Copilot suite: 32 tests, one Windows-only skip. |
| Visual verification | Partial | Previous native Keys & Privacy screenshot confirms the Copilot peer row; this installation was not recompiled or visually rechecked. Required SCIDE-launched sign-off on Windows 10 x64 and MacBook Neo remains open. |

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
- Python 3.11+ setup, GitHub browser sign-in, and a live Copilot request remain
  user-side acceptance steps; this host currently has Python 3.9.6 and no
  Homebrew.
- No live OpenAI/Anthropic request has been made (by design; requires the
  owner's key and consent).
- Prices change; the rate table must be refreshed (it labels itself stale
  after 45 days).

## Open questions and next task

- SCIDE-launched visual sign-off on the MacBook Neo and on a physical
  Windows 10/11 PC with the zip package (`VISUAL_TEST_PLAN.md`).
- Install Python 3.11+ through the Copilot setup helper, finish browser sign-in,
  and verify live Copilot model refresh and generation.
- Owner-run live smoke test with a real API key and a spending limit; live
  OpenAI/Anthropic requests remain opt-in.
