# Decision record — Copilot telemetry hardening replacement

- **Exact branch:** `ralph/copilot-telemetry-hardening-20261008-3515844-ci2`
- **Base `origin/main`:** `3515844e4db4b7a6a58a2d1ed1a49b9e518cc8a5`
- **Implementation commit:** `5c6db42ca8b0171287a26563901e8e2222b360ad`
- **PR:** Not opened yet; this pending record will be moved to a numbered
  PR record through the repository's follow-up status process.

## Decisions

### Disable both Copilot SDK telemetry mechanisms

- **Context:** The existing privacy promise states that telemetry and usage
  history do not leave the machine except as part of a user-initiated model
  request. Copilot SDK 1.0.16 treats any non-null client telemetry config as
  enabled and separately defaults session telemetry on for
  GitHub-authenticated sessions.
- **Alternatives:** Keep `telemetry={"enabled": False}`; disable only client
  OpenTelemetry; or rely on the SDK's default for session telemetry.
- **Rationale:** SDK 1.0.16 documents `enable_session_telemetry=False` as the
  control for session telemetry and maps it to the runtime payload. Omitting
  client telemetry config avoids enabling instrumentation; filtering inherited
  `COPILOT_*` and `OTEL_*` variables prevents ambient settings from enabling
  exporters.
- **Consequences:** Both SDK telemetry channels are explicitly disabled while
  the requested Copilot model connection remains available. Regression tests
  verify the two settings and inherited environment filtering. Active GUI and
  physical Windows acceptance are not established by these tests.

### Preserve PR #54 and use a fresh replacement branch

- **Context:** PR #54 is published and its hosted checks passed, but its
  session-level telemetry setting remained enabled by SDK default.
- **Alternatives:** Merge the incomplete branch or attempt to update its
  published head.
- **Rationale:** Neither action is acceptable under the privacy promise and
  repository branch policy. A fresh branch from current `origin/main` avoids
  mutating the published PR.
- **Consequences:** PR #54 remains preserved and unmerged until the complete
  replacement branch is integrated; it should then be closed as superseded.

## Unresolved gates

- PR, hosted checks, independent exact-head reviews, and remote merge
  verification are pending.
- The user instructed that the running SuperCollider application must not be
  altered. Active-window verification and physical Windows visual acceptance
  remain open.
