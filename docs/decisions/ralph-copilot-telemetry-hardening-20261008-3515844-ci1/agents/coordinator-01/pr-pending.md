# Copilot telemetry privacy hardening — PR pending

- **Run/task:** `copilot-setup-onboarding-20261007-1640` /
  `copilot-runtime-setup-onboarding`
- **Branch:** `ralph/copilot-telemetry-hardening-20261008-3515844-ci1`
- **Worktree:** `/Users/jrblankenhorn/dj_maxxed_beats.worktrees/ralph-copilot-telemetry-hardening-20261008-3515844-ci1`
- **Base `origin/main`:** `3515844e4db4b7a6a58a2d1ed1a49b9e518cc8a5`
- **Project decision:** [DEC-047](../../../../decision_log.md#dec-047--leave-copilot-sdk-telemetry-disabled)
- **Implementation commit:** `9b936df7b4787e2d3bb02ab60ee2eaa50216a704`
- **Pull request:** not opened

## Root cause and correction

Copilot SDK 1.0.16 sets `COPILOT_OTEL_ENABLED=true` whenever the client
receives a non-null telemetry configuration. The existing
`telemetry={"enabled": false}` therefore enabled instrumentation instead of
disabling it. The bridge also inherited standard `OTEL_*` variables, despite
the product plan's no-telemetry requirement.

The bridge now omits the telemetry argument and removes inherited
`COPILOT_*` and `OTEL_*` variables case-insensitively. The request workspace,
session config isolation, saved authentication home, and tool-denial settings
remain unchanged.

## Verification

- Test-first Red: both telemetry regression tests failed before the production
  change for the expected SDK-config and inherited-environment reasons.
- Green: both regression tests pass.
- Focused Copilot bridge/setup suite: **36 tests passed, 1 skipped**.
- Branch auth-only probe under SCIDE's system-only `PATH`: authenticated
  successfully with the user's saved login.
- Full headless gate: **238 tests passed, 7 skipped** in **343.896 seconds**.

## Acceptance still open

This is a source-branch verification. The merged auth-home fix and this
telemetry correction have not yet been installed into the active SCIDE
extension. In-window model refresh and a real GUI request remain unverified.
Physical Windows 10 x64 visual acceptance is also open.
