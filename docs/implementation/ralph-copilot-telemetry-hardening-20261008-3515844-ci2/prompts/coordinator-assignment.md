# Coordinator assignment

Implement the smallest complete fix for the Copilot SDK 1.0.16 privacy
contract. First add and run a failing regression for
`enable_session_telemetry=False`; also retain tests proving client
OpenTelemetry is not configured and inherited `COPILOT_*`/`OTEL_*` settings
are filtered case-insensitively. Preserve PR #54 and work only on a fresh
branch from `origin/main`.

Run the focused Copilot tests and the repository-required
`bash scripts/run_headless_tests.sh` gate. Record exact Red/Green results,
open GUI/platform limitations, and the current branch state. Before merge,
obtain exact-head code and security reviews using GPT-6.1 Luna; do not use
Opus for this routine review. Do not make a live provider call, install into,
restart, or otherwise alter the user's running SuperCollider application.
