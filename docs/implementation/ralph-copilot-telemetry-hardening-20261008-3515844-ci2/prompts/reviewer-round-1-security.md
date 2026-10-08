# Security reviewer prompt — round 1

Use the GPT-6.1 Luna model. Review the exact current PR base/head pair supplied
at dispatch; record both full SHAs and do not review a stale branch tip.
Read-only review: do not edit, commit, push, or merge.

Inspect the Copilot SDK client/session configuration and subprocess
environment boundary against the project's no-telemetry promise. Verify from
the pinned SDK 1.0.16 API semantics that omitting client telemetry config and
passing `enable_session_telemetry=False` disable distinct telemetry paths.
Check that filtering `COPILOT_*`/`OTEL_*` variables case-insensitively does
not leak ambient exporter settings or credentials, and that errors/tests do
not expose secrets. Report only high-confidence security/privacy findings.
Do not use Opus for this review.
