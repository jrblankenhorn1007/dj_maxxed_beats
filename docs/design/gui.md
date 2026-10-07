# MaxxedBeats assistant GUI — design (worker-03)

Scope: `extension/Classes/MaxxedBeats.sc`, `extension/Classes/GUI/`, help,
`scripts/install_maxxedbeats.py`, `.github/workflows/assistant-tests.yml`,
and their tests. Interfaces of other layers are fixed by
[CONTRACT.md](./CONTRACT.md); this document defines the GUI's own port.

## Structure

| Class | Role |
| --- | --- |
| `MaxxedBeats` | SCIDE entry point (`MaxxedBeats.gui`), single-window management, and the one wiring factory `MaxxedBeats.services(lookup)`. |
| `MBGuiController` | All state and actions; no Qt. Talks only to the service port. Notifies dependants with `changed(\state)`. |
| `MBGuiWindow` | Qt views. Builds widgets, forwards actions, redraws everything from controller state. `views` maps stable names to widgets for tests and drivers. |
| `MBMaskedField` | Masked API-key entry (see below). |
| `MBGuiFormat` | Pure formatting: usage/cost labels, model labels, render checks, diffs, error text, secret redaction. |
| `MBGuiAudition` | Optional live preview of a rendered WAV on the user's running server, and Reveal in file browser. |

## Service port

`MBGuiController` receives an Event of functions, called with `.value`
(never as methods, so Event method names such as `at`, `render`, and `stop`
cannot collide). Callbacks must run on `AppClock` (contract). Records are
read with `at`, so Events or dictionaries both work; `edits` elements are
read with `.path`, `.isNew`, `.diffString` (MBEdit or an Event).

| Function | Arguments → result |
| --- | --- |
| `providers` | → `[(id:, displayName:, requiresKey:)]` |
| `hasKey` | `id, onResult(Boolean)` |
| `storeKey` / `removeKey` / `validateKey` | `id, [key,] onSuccess, onFailure` |
| `refreshModels` | `id, onSuccess, onFailure` (the controller then re-reads `models`) |
| `models` / `lastRefreshed` / `isStale` / `selectedModel` | `id` → contract values |
| `selectModel` | `id, modelId` |
| `sessionTotals` / `history` / `clearHistory` | meter values (`sessionTotals` may add `requests:`) |
| `openProject` | `dir, onSuccess((root:, files:, project:)), onFailure` |
| `projectFiles` (optional) | `project` → relative paths |
| `propose` | `project, providerId, modelId, prompt, context, onSuccess(proposal), onFailure` → handle |
| `apply` | `project, proposal, confirmed, onSuccess, onFailure` |
| `undo` | `project, onSuccess, onFailure` |
| `render` | `project, entryPath, settings, approved, onProgress, onSuccess, onFailure` → handle |
| `startVariations` | `project, providerId, modelId, prompt, maxCandidates, onCandidate, onDone, onFailure` → session |
| `stopVariations` / `applyVariation` | `session` / `session, index, confirmed, onSuccess, onFailure` |
| `cancel` | `handle` |
| `play` / `stopPlayback` / `reveal` | `path, onStarted, onDone, onFailure` → handle / `handle` / `path` |

`context` is `(files: [selected relative paths], entry:, history: [(role:,
content:)])`. `onProgress` may pass a Number in 0..1 or `(fraction:,
message:)`. A candidate is shown from `seed`, `summary`/`plan`, `checks`, and
its audio path `renderPath`, `render[\path]`, or `audioPath`; its index for
`applyVariation` is its 0-based position in arrival order.

`MaxxedBeats.services` maps the port onto the contract classes, looked up by
name (`MBProviderRegistry.default`, `MBCredentialStore.default`; catalog and
meter via `.default` when defined, else `.new`; `MBProject.open`,
`MBAgent.new(project, provider, catalog, meter)`, `MBRenderer.render`,
`MBVariationSession.new(agent, project, max)`). Before `propose` and
`startVariations` it checks that `catalog.selectedModel(providerId)` equals
the model shown in the window and otherwise fails with `\unavailableModel`.
Missing classes raise `MBError(\config)`; `MaxxedBeats.gui` then opens with
`unavailableServices`, which reports that error for every action.

## Safety rules (enforced by the controller and tested)

- Writing files (Approve, Apply candidate), Undo, Render, Remove key, and
  Clear history set `pendingConfirm`; only **Confirm** runs them, and the
  service receives `confirmed: true` / `approved: true` only then.
- The GUI never evaluates code: no `interpret`, `executeFile`, `compile`, or
  `load` in GUI sources (static test). Rendering is delegated to the renderer,
  which evaluates in a separate process.
- No silent fallback: the persisted model stays selected even when missing or
  unusable, is labelled, and blocks requests; unusable models cannot be
  selected; provider/model cannot change while work is running.
- Requests are blocked with a visible reason when no project is open, the
  provider needs a key that is missing, no usable model is selected, the
  prompt is empty, or a proposal is still pending review.
- Late callbacks are ignored after Cancel, after a newer operation, or after
  the window closes (operation tokens). Closing cancels running work, stops
  variations and playback.
- Errors are normalized to `MBError`, redacted (`sk-…`, `Bearer …`,
  `x-api-key`, and the key just entered), shown in the error row and, for
  requests, in the conversation. Status never reports success after a failure.
- Unknown USD/credits are "unavailable"; rates are labelled MISSING or STALE;
  zero is never substituted.
- Variation sessions are capped at 1–4 candidates; extra candidates are
  ignored and the session is stopped at the cap.

## Masked key entry

SuperCollider's Qt `TextField` has no password mode. `MBMaskedField` draws
the field's text in a transparent colour and, on every key press (deferred
one tick so pastes are included), moves the field's contents into an
in-memory buffer and empties the field. A separate label shows up to 12 `*`
and the character count. Backspace removes the last character; mid-key
editing is not supported (use Clear). The key is read once on Save, passed to
`storeKey`, and the buffer is cleared. The GUI never posts, logs, or stores it.

## Tests

- `tests/test_mb_gui.py` runs `tests/mb_gui/gui_state_tests.scd` (≈170 checks)
  and `tests/mb_gui/entry_tests.scd` through a wrapper that always exits
  sclang, with isolated `HOME`/XDG/`LOCALAPPDATA`/`APPDATA`. The window is
  built (not shown) with `tests/mb_gui/fake_services.scd`, whose
  `propose`/`render`/`apply`/`undo`/variation callbacks are fired by the test,
  so busy, cancel, late-callback, and failure paths are deterministic. Qt
  reports widgets of an unshown window as invisible, so the window tracks
  intended visibility (`isShown`). Factory tests use
  `tests/mb_gui/stubs/MBTestStubs.sc` (contract stand-ins with distinct names).
- `tests/test_mb_install.py` covers the installer with a fake ChaosOsc build
  plus an installed-layout sclang compile; `tests/test_mb_install_workflow.py`
  checks the CI workflow contract.
- `tests/mb_gui/capture_screenshots.py` (opt-in, macOS) runs
  `visual_scenario.scd`, which opens the real window via `MaxxedBeats.gui`,
  drives the widgets through ten states, and captures the native window with
  `screencapture -l <CGWindowID>` (window found by sclang's PID through
  CoreGraphics via ctypes). It synchronizes through `MB_CAPTURE_READY` lines
  and `.ack` files. It is evidence for, not a substitute of, the SCIDE sign-off.

## Decisions

1. GUI ↔ services through an Event-of-functions port, not direct calls on
   contract objects: avoids Event/Object selector collisions in fakes and keeps
   real wiring in one factory.
2. Confirmation is an in-window panel, not a modal OS dialog, so it is visible
   above every tab and drivable by tests and the visual driver.
3. Single window per session; `MaxxedBeats.gui` fronts an open window.
4. Context sent to providers is opt-in per file; none selected means prompt
   and conversation only.
5. Installer copies the Quark (plus `agent/*.md` into `MaxxedBeats/agent/`)
   via a staging folder and delegates ChaosOsc to `install_chaososc.py`;
   both targets are pre-checked before any change, and one combined "Next
   steps" block is printed.
6. CI installs with the combined installer into a workspace folder, runs
   `test_mb_*.py`, and uninstalls, on macOS 14 and Windows.
