# Branch decisions — Copilot telemetry hardening replacement

- **Exact branch:** `ralph/copilot-telemetry-hardening-20261008-3515844-ci2`
- **Base `origin/main`:** `3515844e4db4b7a6a58a2d1ed1a49b9e518cc8a5`
- **Implementation commit:** `5c6db42ca8b0171287a26563901e8e2222b360ad`
- **PR record:** [pending](./agents/coordinator-01/pr-pending.md)
- **Product decision:** [DEC-047](../../decision_log.md#dec-047--disable-both-copilot-sdk-telemetry-channels)

## Decisions

1. Disable client OpenTelemetry by omitting the SDK's `telemetry` argument,
   filter inherited `COPILOT_*`/`OTEL_*` variables case-insensitively, and
   explicitly disable GitHub-session telemetry with
   `enable_session_telemetry=False`.
2. Preserve published PR #54 unchanged and unmerged. Its security review
   exposed the separate session-telemetry default; this fresh branch from
   `origin/main` carries the complete fix.
3. Use GPT-6.1 Luna for independent code/security review; do not use Opus for
   this routine review.
