# Branch dossier — Copilot telemetry hardening replacement

- **Exact branch:** `ralph/copilot-telemetry-hardening-20261008-3515844-ci2`
- **Branch slug:** `ralph-copilot-telemetry-hardening-20261008-3515844-ci2`
- **Run/task:** `copilot-setup-onboarding-20261007-1640` /
  `copilot-runtime-setup-onboarding`
- **Coordinator:** `coordinator-01 / Copilot telemetry hardening replacement`
- **Base `origin/main`:** `3515844e4db4b7a6a58a2d1ed1a49b9e518cc8a5`
- **Implementation commit:** `5c6db42ca8b0171287a26563901e8e2222b360ad`
- **State:** local focused and full headless gates pass; branch records are
  being completed before publication. PR #54 is preserved and must not merge.
- **Scope:** disable both Copilot SDK client OpenTelemetry and
  GitHub-authenticated session telemetry, and filter inherited telemetry
  environment variables.
- **User request:** [summary](./prompts/user-request.md)
- **Coordinator assignment:** [scope](./prompts/coordinator-assignment.md)
- **Handoff:** [coordinator-01](./agents/coordinator-01/handoff.md)
- **Decisions:** [branch index](./decisions/README.md)
- **Code review:** [review state](./code-review/README.md)
- **Ralph records:** [status](../../ralph/ralph-copilot-telemetry-hardening-20261008-3515844-ci2/agents/coordinator-01/status.md)
  and [progress](../../ralph/ralph-copilot-telemetry-hardening-20261008-3515844-ci2/agents/coordinator-01/progress.md)
- **Project decision:** [DEC-047](../../decision_log.md#dec-047--disable-both-copilot-sdk-telemetry-channels)
- **Previous attempt:** [PR #54](https://github.com/jrblankenhorn1007/dj_maxxed_beats/pull/54)
  remains unmerged because it omitted the session-level telemetry opt-out.
