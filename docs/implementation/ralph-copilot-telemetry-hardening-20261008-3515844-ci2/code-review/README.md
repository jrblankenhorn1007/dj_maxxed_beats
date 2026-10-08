# Code review state — Copilot telemetry hardening replacement

- **Status:** PENDING exact-head review.
- **Rounds completed:** 0 of 2.
- **Required reviewers:** Ralph Code Reviewer and Ralph Security Reviewer.
- **Requested model:** GPT-6.1 Luna; do not use Opus for this task.
- **Review prompts:** [code](../prompts/reviewer-round-1-code.md) and
  [security](../prompts/reviewer-round-1-security.md).
- **Exact base/head:** to be recorded from the published PR immediately before
  dispatch; no review report is available yet.
- **PR #54 context:** a security review found the SDK's separate session
  telemetry remained enabled by default. PR #54 is intentionally not merged;
  this replacement explicitly disables that option.

Per the project review protocol, keep reviewer reports as sidecar evidence
while the PR is open. Archive the immutable reports only after integration.
