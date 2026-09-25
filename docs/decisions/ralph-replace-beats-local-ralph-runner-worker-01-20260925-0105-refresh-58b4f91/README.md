# Branch decisions

- **Exact branch:** `refs/heads/ralph/replace-beats-local-ralph-runner-worker-01-20260925-0105-refresh-58b4f91`
- **Branch slug:** `ralph-replace-beats-local-ralph-runner-worker-01-20260925-0105-refresh-58b4f91`
- **Run/task:** `ralph-shared-workflow-move-20260925-0105` /
  `replace-beats-local-ralph-runner`
- **Worker:** `worker-01 / Beats workflow migration` (`runtime_agent_id: null`)
- **Base:** `58b4f916603cc8e140c5e8c1bbca1290bb2dede6`
- **Implementation commit:** `6e13eeea00bbbfb7a046926c4e0732beb05e9a8b`
- **PR record:** [worker-01 pending PR](./agents/worker-01/pr-pending.md)

This replacement branch carries the workflow migration from the preserved
published branch based on `b1c77ae`; it was created because `origin/main`
advanced to this branch's base before PR creation. The older branch is recorded
as cancelled under its own branch slug. The coordinator owns
`docs/ralph-status.md`; this branch contains only the assigned worker's
branch-scoped status, progress, and decision records.
