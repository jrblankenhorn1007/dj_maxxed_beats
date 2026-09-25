# Agent / PR record — coordinator-01 — PR pending

- **Run/task:** `branch-evidence-dossiers-20260925-081730` /
  `document-branch-evidence-dossiers`
- **Coordinator:** `coordinator-01 / branch evidence archive`
- **Runtime/session ID:** `ac00179e-f9e2-4693-8f9f-710a82b06af9`
- **Branch:** `ralph/implementation-records-coordinator-20260925-081730`
- **Base `origin/main`:** `7523a9a0b87ffc5304686e2e64509fc4a6941bb7`
- **Implementation commit:** pending
- **Pull request:** pending normal publication to `main`.
- **Review:** pending; launch the independent Ralph Code Reviewer for the
  exact PR base/head SHAs before any merge action. The changes are
  documentation-only and do not trigger the conditional security reviewer.
- **Merge:** not attempted; no `origin/main` integration is claimed.

## Decision

- **Context:** The shared Ralph workflow already stores branch status,
  progress, and PR decisions in separate branch-scoped directories. The
  project needs one branch-keyed entry point for locating those records,
  author/reviewer prompts, agent handoffs, and structured code-review
  reports.
- **Decision:** Add `docs/implementation/<branch-slug>/` as an index and
  evidence archive. Keep existing shared-skill status/progress and decision
  histories at their canonical paths and link to them; do not move or
  duplicate their full history. Give every dossier a `code-review/` folder,
  including historical or no-PR branches, with an explicit recorded status.
- **Review safety:** Bind every review record to exact full base/head SHAs.
  Capture interim reports as sidecar evidence while the PR is open and archive
  them after integration, so saving a report does not mutate the reviewed PR
  head or base. Follow the canonical independent reviewer roles and two-round
  limit.
- **Historical evidence:** Do not invent prompts, transcripts, review
  outcomes, or author decisions that were not preserved. Label unavailable
  records as legacy/unarchived and link to the closest existing evidence.
- **Alternatives:** Move the existing Ralph and decision trees into the new
  hierarchy, or keep the current scattered organization without a branch
  index.
- **Rationale:** An additive index preserves stable paths already used by
  shared skills and project history while providing one branch-local home for
  future prompts, handoffs, and review artifacts.

## Integration path

Worker-01 (`ed746241-112c-4f2e-a0e8-319ab408fd18`) reported a blocker before
implementation: its session could not create or modify repository artifacts.
No child worktree, branch, files, commit, or sign-off resulted. The coordinator
continues the task in the isolated parent worktree; no replacement worker was
dispatched because the assignment is one cohesive documentation scope.

## Recovered verification issue

The first local Markdown-link check reported only the plan's pre-existing
`../supercollider/` references, whose optional read-only checkout is absent
from the fresh worktree. Re-running the check while excluding only those
unchanged targets passed for all new and changed documentation. The other
internal links, all 18 dossier/code-review pairs, and the schema-v2 dashboard
checks passed. No product behavior tests were run because this change is
documentation-only.
