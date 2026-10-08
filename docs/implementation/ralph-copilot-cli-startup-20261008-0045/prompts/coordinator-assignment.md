# Coordinator assignment

## Outcome

Fix the live Copilot SDK startup failure on the fresh branch and prove the
actual bridge/provider path works with the installed private runtime.

## Acceptance criteria

- The bridge uses the SDK-compatible stdio runtime rather than passing the
  standalone interactive CLI and unsupported CLI flags.
- The existing tool-denial boundary is preserved and checked before
  generation.
- The platform setup path pre-downloads the SDK-matched runtime using a
  trusted CA bundle.
- Regression tests reproduce the old configuration and pass with the fix.
- The required headless project gate passes.
- Live auth, model refresh, and one short Copilot request succeed without
  exposing credentials.

## Owned paths

- `extension/Data/copilot/bridge.py`
- `extension/Data/copilot/setup_copilot.py`
- `tests/test_mb_copilot.py`
- `tests/test_mb_copilot_setup.py`
- User, decision, status, progress, and branch-dossier records for this branch.

No implementation workers were dispatched: the bridge selection, setup
provisioning, tool-denial invariant, and tests are one coupled runtime
contract. Independent code and security review are required before merge.
