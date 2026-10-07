# Implementation Status

> Current-state snapshot stored in `docs/implementation_status.md`.
>
> This snapshot is rewritten each iteration; `RALPH_PROGRESS.md` holds
> per-iteration test evidence, and `decision_log.md` is append-only.

## Latest loop report

- **Completed implementation iteration:** `7` — the MaxxedBeats AI assistant
  (parent branch `ralph/ai-assistant-20261007`; worker-01 providers,
  worker-02 workflow, worker-03 GUI/packaging/CI, then integration).
- **Loop state:** integrated on the parent branch and verified by the full
  headless gate on a MacBook Neo; GitHub CI verified on a `-ciN` branch
  (see `RALPH_PROGRESS.md`). Not merged to `main`; no PR yet.
- **Delivered:** in-SuperCollider assistant window (`MaxxedBeats.gui`),
  OpenAI/Anthropic/mock providers over OS `curl`, OS credential stores,
  model catalog, usage/cost/credits, project review/apply/backup/undo,
  approved separate-process NRT rendering with audio checks, a bounded
  variation loop, a combined Quark + ChaosOsc installer, help, user guide,
  and an **Assistant Tests** CI workflow (macOS and Windows).

## Overall state

The assistant works end to end on macOS with the offline mock provider:
open the window from SCIDE, choose your DJ, propose, review the diff,
confirm the apply (with backup), approve a render that produces a real WAV
with ChaosOsc and checks, undo, and run a variation session with approved
renders and a confirmed apply. Live OpenAI/Anthropic calls are implemented
and tested against loopback fake servers; no billable call has been made.
Windows is CI-tested only; physical Windows 10 x64 and SCIDE-launched visual
sign-off remain open.

## Component status

| Area | Status | Current state |
| --- | --- | --- |
| ChaosOsc server plugin | Implemented | `ChaosOsc.ar`/`.kr(chaosAmount, seed, freq, mul, add)`; CMake build for macOS (universal), Linux, Windows (MSVC). |
| SCIDE entry point and window | Implemented | `MaxxedBeats.gui`: project, Choose your DJ (explicit provider/model ids, refresh, stale/unavailable labels, no fallback), conversation, plan (with assumptions/uncertainty/questions), diff review, confirmations, render panel, Play/Reveal, usage, history, variations, keys and privacy notice. [GUI design](./design/gui.md). |
| Providers and transport | Implemented (macOS verified) | Direct sclang + OS `curl`, no helper; TLS enforced; cancellable; keys never in argv/env. Windows transport designed, not runtime-verified. [Provider design](./design/providers.md). |
| Credentials | Implemented (macOS verified) | macOS Keychain via `security`; Windows Credential Manager (PowerShell) and Linux Secret Service designed and command-tested only; in-memory fake for tests. |
| Model catalog | Implemented | Per-provider refresh/cache/selection (`model-catalog.json`, `providers.json`); never substitutes; stale after failure or 24 h. |
| Usage, USD, credits | Implemented | Versioned rate table `2026-10-06.1`; 100 credits per estimated USD; missing/stale labelled, never zero; local history (`usage-history.json`). |
| Project, proposals, apply, undo | Implemented | Strict `maxxedbeats.proposal/1`; path confinement; confirmed apply with backups; undo refuses after later user edits. [Workflow design](./design/workflow.md). |
| Rendering | Implemented (macOS verified) | Approved only; separate `sclang` → Score → `scsynth -N` with `env -i` and isolated HOME; checks and JSON sidecar. Windows/Linux launching unverified. |
| Variation loop | Implemented | User-started, 1–4 candidates in the GUI (session caps at 16), isolated copies, fixed seeds, renders only with explicit approval, confirmed apply. |
| Mock provider | Implemented | Deterministic `maxxedbeats.proposal/1` replies with a seed-dependent ChaosOsc composition; drives tests and the visual scenario. |
| Packaging | Implemented | `scripts/install_maxxedbeats.py` installs/removes the Quark (with `agent/*.md`) and ChaosOsc together; marker-protected; dry run. |
| Documentation | Implemented | [User guide](./USER_GUIDE.md), README, SCDoc help, three design docs. |
| Tests and CI | Implemented | `bash scripts/run_headless_tests.sh` (all suites, including GUI state, provider, workflow, render, integration). **Assistant Tests** (macOS 14 + Windows), **Headless Tests** (macOS 14), **Plugin Builds** (three OSes). Header downloads retry with backoff and are cached in CI. |
| Visual verification | Partial | Native-window screenshots of the real window with real renders captured and inspected on the MacBook Neo via `tests/mb_gui/capture_screenshots.py` (sclang launch). SCIDE-launched sign-off and Windows are open. |

## Verification and platform coverage

- **MacBook Neo** (`Mac17,5`, macOS 26, SuperCollider 3.14.1): full headless
  gate, GUI integration with real NRT renders, Keychain round trip in a
  temporary keychain, and screenshot capture. See `RALPH_PROGRESS.md`
  (iteration 7) for commands and counts.
- **Windows:** CI only (Assistant Tests on `windows-latest`, Plugin Builds
  with an NRT smoke render). No physical Windows 10 x64 run.
- **Linux:** plugin build and installer in CI; assistant untested.

## Blockers and risks

- Windows transport, credential backend, and render process launching are
  designed but not verified on a Windows desktop; macOS-only test paths are
  skipped there.
- No live OpenAI/Anthropic request has been made (by design; requires the
  owner's key and consent).
- Prices change; the rate table must be refreshed (it labels itself stale
  after 45 days).

## Open questions and next task

- SCIDE-launched visual sign-off on the MacBook Neo and on physical
  Windows 10 x64 (`VISUAL_TEST_PLAN.md`).
- Owner-run live smoke test with a real key and a spending limit.
- Open the PR for `ralph/ai-assistant-20261007` after CI is green.
