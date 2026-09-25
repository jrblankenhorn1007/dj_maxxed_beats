# Coordinator decision record — replacement README integration

- **Run/task:** `readme-refresh-20260925-0248` /
  `improve-root-readme`
- **Coordinator:** `coordinator-01 / README continuation and integration`
- **Branch:** `ralph/readme-documentation-followup-20260925-0412`
- **Worktree:** `/Users/jrblankenhorn/dj_maxxed_beats.worktrees/ralph-readme-documentation-followup-20260925-0412`
- **Starting `origin/main`:**
  `c448dae05f792ef868557e7d67a0a1becb7e6895`
- **Pull request:** pending initial branch publication.

## Decision — continue the README on a fresh branch

- **Context:** The initial README worker published PR #17 and later attempted
  to push handoff records to that already-published branch. GitHub rejected
  the update with GH013. PR #17 then became unmergeable after `origin/main`
  advanced and was closed without merge.
- **Alternatives:** Retry the old branch push, lower or bypass the coverage
  rule, rebase/update the published PR branch, or carry the intended changes
  to a fresh branch.
- **Decision:** Preserve the original branch and closed PR; continue from the
  latest clean `origin/main` on this fresh branch. Complete documentation and
  status commits before its first publication, then use the normal GitHub
  API/UI PR merge path.
- **Rationale:** The authoritative GitHub rule-suite result identifies an
  API/UI-only merge restriction, not a reported measured coverage shortfall.
  A fresh branch avoids retrying a direct update to the published PR branch
  and preserves the original history.
- **Consequences:** No coverage thresholds, tests, or product code are
  changed as a workaround. The implementation and post-merge memory update
  will be independently verified on `origin/main`.

## GH013 evidence

GitHub rule-suite evaluation `4221447764` reports the active `Gate` ruleset's
`code_coverage` rule with the message “Code coverage checks require merging via
API or UI.” The configured minimum is 100 percent, but the rejection did not
report a measured coverage percentage. Treat this as a branch-update/merge
path restriction, not proof that the project's measured coverage is below
the configured minimum.

## Documentation repair and verification plan

The root README is the project landing page; `docs/README.md` is a
documentation index. The implementation plan now links to the developer-check
section of the root README because the former headless-test anchor in
`docs/README.md` no longer exists.

Before initial publication, validate Markdown links and anchors in the root
README, docs index, implementation plan, and decision/status records, and run
`git diff --check`. Product tests are not applicable because this change does
not alter product behavior. After the PR merge, fetch `origin` and verify its
merge SHA on `origin/main`; then review project memory and publish any
warranted lesson through a separate fresh branch and PR.
