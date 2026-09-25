schema_version: 1
run_id: "ralph-shared-workflow-move-20260925-0105"
task_ids: ["replace-beats-local-ralph-runner"]
worker_id: "worker-01"
worker_name: "worker-01 / Beats workflow migration"
runtime_agent_id: null
branch: "ralph/replace-beats-local-ralph-runner-worker-01-20260925-0105"
branch_slug: "ralph-replace-beats-local-ralph-runner-worker-01-20260925-0105"
iteration: 1
status: CANCELLED
started_at_utc: "2026-09-25T01:15:21Z"
updated_at_utc: "2026-09-25T01:22:27Z"
base_origin_main_sha: "b1c77ae9192491a86be5d42e86aebc10e3057a2d"
rebased_onto_origin_main_sha: null
implementation_commit_sha: "78c4347131927190eecb02baad261fdd1f0bb628"
pull_request:
  status: NOT_OPENED
  number: null
  url: null
decision_record_path: "docs/decisions/ralph-replace-beats-local-ralph-runner-worker-01-20260925-0105/agents/worker-01/pr-not-opened.md"
decision_index_path: "docs/decisions/ralph-replace-beats-local-ralph-runner-worker-01-20260925-0105/README.md"
merge_actor_worker_id: null
merge:
  status: NOT_APPLICABLE
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
  - command: "git fetch origin; compare refs/heads/ralph/replace-beats-local-ralph-runner-worker-01-20260925-0105 with 78c4347131927190eecb02baad261fdd1f0bb628"
    result: PASS
blockers: []
next_action: "No action on this superseded branch; the migration continues on the fresh branch based on current origin/main."
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
