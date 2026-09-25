# Git workflow memory

### Use the repository's authorized PR merge path
- **Rule:** For this repository, complete the intended commits before first
  publishing a PR branch. If a post-publication update is rejected by GH013
  under the active `Gate` / `code_coverage` rule, do not retry direct
  `git push`; use the GitHub API/UI path required by the rule.
- **Why:** On 2026-09-25, GitHub rejected a post-publication handoff-record
  push for PR #17. Rule-suite evaluation `4221447764` identified the active
  `code_coverage` rule and said, "Code coverage checks require merging via API
  or UI." The initial branch publication for the replacement PR #20 succeeded,
  its checks passed, and `gh pr merge` integrated it. See the
  [PR #17 diagnosis](../../docs/decisions/ralph-readme-docs-worker-01-20260925-0248/agents/worker-01/pr-17.md)
  and [PR #20 integration record](../../docs/decisions/ralph-readme-documentation-followup-20260925-0412/agents/coordinator-01/pr-20.md).
- **Scope:** This repository while its active `Gate` ruleset requires the
  `code_coverage` rule to merge through GitHub API/UI.
- **Gotcha:** GH013 and the API/UI-only message do not report that measured
  coverage is below the configured minimum. Do not lower coverage thresholds
  or add coverage instrumentation unless a separate coverage result shows an
  actual coverage shortfall.
