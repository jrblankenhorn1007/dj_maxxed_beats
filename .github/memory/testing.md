# Testing memory

### Validate plugins against the tested SuperCollider runtime
- **Rule:** Pin plugin API headers to the official SuperCollider release used by
  the test runtime, then load and render the UGen in that runtime's NRT server.
  Cover supported audio-rate and control-rate inputs and verify deterministic
  repeated renders.
- **Why:** Iteration 5's development headers reported API version 7 while
  SuperCollider 3.14.1 expected version 3. After pinning the release headers,
  NRT testing exposed a control-rate buffer over-read that compile and
  source-contract checks had not caught. See
  [DEC-022](../../docs/decision_log.md).
- **Scope:** SuperCollider plugin and UGen changes.

### Keep headless NRT plugin search paths unique
- **Rule:** Resolve and de-duplicate the `-U` plugin search paths before
  launching `scsynth`, and use `-D 0` when the NRT test must not load a user's
  default synthdefs.
- **Why:** Passing the same built-in plugin directory twice caused the
  iteration 5 NRT server to abort; de-duplicating the resolved paths and
  disabling default synthdef loading fixed the harness. See
  [iteration 5 verification](../../docs/RALPH_PROGRESS.md).
- **Scope:** This project's headless SuperCollider NRT test harness.

### Parse SuperCollider help with the real SCDoc parser
- **Rule:** Validate every `.schelp` file with `sclang`'s `SCDoc.parseFileFull`
  in the test suite; text or contract checks do not prove the help renders.
- **Why:** `ChaosOsc.schelp` passed the source-contract test, but SCDoc 3.14.1
  rejected a bare `::` outside a tag, so the help page never rendered. See
  [DEC-029](../../docs/decision_log.md).

### Isolate sclang user folders in headless tools
- **Rule:** Run headless `sclang` (tests and render scripts) with an isolated
  `HOME`/XDG/`LOCALAPPDATA` and explicit `--include-path` entries so installed
  extensions cannot duplicate repository classes.
- **Why:** After installing ChaosOsc into the user Extensions folder,
  `render_composition.py` failed with `duplicate Class found: 'ChaosOsc'`
  until its `sclang` ran in a temporary language home (PR #34 review R1).
- **Gotcha:** On Windows, SuperCollider resolves user folders through the
  known-folder API, not environment variables, so this isolation does not
  apply there.

### Pin an output-only device for real-time macOS server tests
- **Rule:** Set `ServerOptions.device` to an output-only CoreAudio device for
  automated real-time `scsynth` runs, and reject device names containing
  shell-significant characters.
- **Why:** With SuperCollider 3.14.1, `numInputBusChannels = 0` still opened
  the default input (the microphone) when it differed from the output, which
  raised a macOS privacy prompt and stalled boot. `Server:boot` passes the
  `-H` device name to `/bin/sh` with quotes but no escaping (PR #34 security
  review S3).

### Record the actual hardware model with platform evidence
- **Rule:** Capture `system_profiler SPHardwareDataType` (model name and
  identifier) whenever recording device-specific verification.
- **Why:** The 2026-10-06 verification host turned out to be an actual
  MacBook Neo (`Mac17,5`), a target-device acceptance gate that earlier
  records had labeled as unverified without checking the model.
