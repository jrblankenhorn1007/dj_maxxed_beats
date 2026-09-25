schema_version: 1
run_id: "ralph-shared-workflow-move-20260925-0105"
task_ids: ["replace-beats-local-ralph-runner"]
worker_id: "worker-01"
worker_name: "worker-01 / Beats workflow migration"
runtime_agent_id: null
branch: "ralph/replace-beats-local-ralph-runner-worker-01-20260925-0105"
branch_slug: "ralph-replace-beats-local-ralph-runner-worker-01-20260925-0105"
iteration: 1
status: IN_PROGRESS
started_at_utc: "2026-09-25T01:15:21Z"
updated_at_utc: "2026-09-25T01:15:21Z"
base_origin_main_sha: "b1c77ae9192491a86be5d42e86aebc10e3057a2d"
rebased_onto_origin_main_sha: null
implementation_commit_sha: null
pull_request:
  status: PENDING
  number: null
  url: null
decision_record_path: "docs/decisions/ralph-replace-beats-local-ralph-runner-worker-01-20260925-0105/agents/worker-01/pr-pending.md"
decision_index_path: "docs/decisions/ralph-replace-beats-local-ralph-runner-worker-01-20260925-0105/README.md"
merge:
  status: PENDING
  sha: null
  verified_remote_ref: "refs/heads/main"
  verified_origin_main_sha: null
  verification_method: null
  verified_at_utc: null
checks:
  - command: "git diff --check"
    result: PASS
  - command: "active instruction git grep for local runner paths/flags"
    result: PASS
  - command: "test local runner and runner-only test files are absent"
    result: PASS
blockers:
  - "GitHub CLI is unavailable; the normal PR creation path is not yet established."
next_action: "Finish the migration commit, publish the branch, and use the repository's normal PR path."
worker_sign_off:
  status: NOT_RECEIVED
  attestation_kind: null
  cryptographic_signature_status: NOT_CRYPTOGRAPHICALLY_SIGNED
  attested_at_utc: null
  statement: null
commit_signature_verification:
  status: NOT_CRYPTOGRAPHICALLY_SIGNED
  verifier: null
  evidence: null
  verified_at_utc: null
