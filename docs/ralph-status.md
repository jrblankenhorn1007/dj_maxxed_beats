schema_version: 1
snapshot_path: "docs/ralph-status.md"
snapshot_revision: 1
updated_at_utc: "2026-09-25T01:34:39Z"
overall_status: IN_PROGRESS
current_run_ids: ["ralph-shared-workflow-move-20260925-0105"]

runs:
  - run_id: "ralph-shared-workflow-move-20260925-0105"
    task_ids: ["replace-beats-local-ralph-runner"]
    aggregate_status: IN_PROGRESS
    requested_worker_count: 2
    effective_worker_count: 1
    active_worker_count: 0
    base_origin_main_sha: "58b4f916603cc8e140c5e8c1bbca1290bb2dede6"
    created_at_utc: "2026-09-25T01:15:21Z"
    updated_at_utc: "2026-09-25T01:34:39Z"
    next_action: "Coordinator: merge PR #8 through the normal repository process, verify the resulting SHA on fetched origin/main, and complete the post-merge memory review."
    split_plan:
      - task_id: "replace-beats-local-ralph-runner"
        worker_id: "worker-01"
        scope: "Remove the Beats-local Ralph runner and direct the project prompt and active documentation to the canonical shared Ralph Loop agent and skill."
        depends_on: []
    worker_count_note: "Only one assignment was ready: the shared Ralph Loop skill and agent already existed, and the Beats migration was a single cohesive scope."

branch_agent_index:
  - run_id: "ralph-shared-workflow-move-20260925-0105"
    task_ids: ["replace-beats-local-ralph-runner"]
    worker_id: "worker-01"
    worker_name: "worker-01 / Beats workflow migration"
    branch: "ralph/replace-beats-local-ralph-runner-worker-01-20260925-0105"
    branch_slug: "ralph-replace-beats-local-ralph-runner-worker-01-20260925-0105"
    status: CANCELLED
    iteration: 1
    status_path: "docs/ralph/ralph-replace-beats-local-ralph-runner-worker-01-20260925-0105/agents/worker-01/status.md"
    progress_path: "docs/ralph/ralph-replace-beats-local-ralph-runner-worker-01-20260925-0105/agents/worker-01/progress.md"
    decision_record_path: "docs/decisions/ralph-replace-beats-local-ralph-runner-worker-01-20260925-0105/agents/worker-01/pr-not-opened.md"
    decision_index_path: "docs/decisions/ralph-replace-beats-local-ralph-runner-worker-01-20260925-0105/README.md"
    next_action: "None; preserve this superseded branch and continue on the fresh branch created from updated origin/main."
  - run_id: "ralph-shared-workflow-move-20260925-0105"
    task_ids: ["replace-beats-local-ralph-runner"]
    worker_id: "worker-01"
    worker_name: "worker-01 / Beats workflow migration"
    branch: "ralph/replace-beats-local-ralph-runner-worker-01-20260925-0105-refresh-58b4f91"
    branch_slug: "ralph-replace-beats-local-ralph-runner-worker-01-20260925-0105-refresh-58b4f91"
    status: AWAITING_MERGE
    iteration: 1
    status_path: "docs/ralph/ralph-replace-beats-local-ralph-runner-worker-01-20260925-0105-refresh-58b4f91/agents/worker-01/status.md"
    progress_path: "docs/ralph/ralph-replace-beats-local-ralph-runner-worker-01-20260925-0105-refresh-58b4f91/agents/worker-01/progress.md"
    decision_record_path: "docs/decisions/ralph-replace-beats-local-ralph-runner-worker-01-20260925-0105-refresh-58b4f91/agents/worker-01/pr-8.md"
    decision_index_path: "docs/decisions/ralph-replace-beats-local-ralph-runner-worker-01-20260925-0105-refresh-58b4f91/README.md"
    pull_request:
      number: 8
      url: "https://github.com/jrblankenhorn1007/dj_maxxed_beats/pull/8"
      state: OPEN
      mergeable: MERGEABLE
    checks:
      - command: "git diff --check and active-instruction runner-reference checks"
        result: PASS
      - command: "GitHub PR #8 status query"
        result: PASS
      - command: "GitHub check-run list"
        result: PASS (none reported)
    merge_verification:
      status: PENDING
      merge_sha: null
      verified_origin_main_sha: null
    next_action: "Coordinator: merge PR #8, fetch origin, verify the merge SHA on origin/main, and complete the post-merge memory review."
