# Coordinator assignment

## Outcome

Preserve the implementation plan's no-telemetry guarantee for the Copilot
SDK runtime without changing the auth-home, per-request session isolation, or
tool-denial behavior.

## Acceptance criteria

- The bridge does not pass an SDK telemetry configuration.
- Inherited `COPILOT_*` and standard `OTEL_*` environment variables do not
  reach the provider subprocess, regardless of key casing.
- Regression tests reproduce both incorrect behaviors and pass after the
  minimal production change.
- The focused Copilot suite and full headless gate pass.
- The bridge still authenticates with the user's saved Copilot login under
  SCIDE's system-only `PATH`.
- In-window model refresh and a real GUI request are verified after the
  merged change is installed; do not mark complete before that acceptance.

## Owned paths

- `extension/Data/copilot/bridge.py`
- `tests/test_mb_copilot.py`
- `docs/` status, progress, decision, and branch-dossier records for this
  iteration, plus the post-merge PR #53 status/dossier correction.

No implementation workers were launched because the environment had no free
Resource Manager slots and this is a single cohesive runtime/privacy change.
