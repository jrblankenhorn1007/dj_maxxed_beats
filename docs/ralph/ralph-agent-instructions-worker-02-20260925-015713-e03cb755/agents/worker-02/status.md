schema_version: 1
run_id: "ralph-product-end-condition-20260925-015713-e03cb755"
task_ids: ["agent-instruction-contract"]
worker_id: "worker-02"
worker_name: "worker-02 / agent guidance"
runtime_agent_id: null
branch: "ralph/agent-instructions-worker-02-20260925-015713-e03cb755"
branch_slug: "ralph-agent-instructions-worker-02-20260925-015713-e03cb755"
iteration: 1
status: IN_PROGRESS
started_at_utc: "2026-09-25T02:05:52Z"
updated_at_utc: "2026-09-25T02:07:46Z"
base_origin_main_sha: "f9e1bb3edafff1cc6d24c640a8e0ed38f5bf49fe"
rebased_onto_origin_main_sha: null
implementation_commit_sha: null
pull_request:
  status: PENDING
  number: null
  url: null
merge_actor_worker_id: null
decision_record_path: "docs/decisions/ralph-agent-instructions-worker-02-20260925-015713-e03cb755/agents/worker-02/pr-pending.md"
decision_index_path: "docs/decisions/ralph-agent-instructions-worker-02-20260925-015713-e03cb755/README.md"
merge:
  status: PENDING
  sha: null
  verified_remote_ref: "refs/heads/main"
  verified_origin_main_sha: null
  verification_method: null
  verified_at_utc: null
checks:
  - command: "PYTHONDONTWRITEBYTECODE=1 python3 tests/test_agent_instructions.py"
    result: PASS
  - command: "PYTHONDONTWRITEBYTECODE=1 python3 tests/test_chaososc_language_contract.py"
    result: PASS
  - command: "git diff --cached --check"
    result: PASS
  - procedure: "SCIDE GUI, provider calls, and SuperCollider runtime validation"
    result: NOT_RUN
blockers: []
next_action: "Finish the scoped diff review and records, commit, publish/open the PR, then await coordinator merge authorization."
worker_sign_off:
  status: PENDING
  attestation_kind: SELF_ATTESTATION
  cryptographic_signature_status: NOT_CRYPTOGRAPHICALLY_SIGNED
  attested_at_utc: null
  statement: null
commit_signature_verification:
  status: NOT_CRYPTOGRAPHICALLY_SIGNED
  verifier: null
  evidence: null
  verified_at_utc: null
