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
