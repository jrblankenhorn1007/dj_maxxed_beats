```yaml
schema_version: 1
run_id: "headless-integration-tests-20260925-0246"
task_ids: ["implement-headless-test-pipeline"]
worker_id: "worker-01"
worker_name: "worker-01 / headless test pipeline"
runtime_agent_id: null
branch: "ralph/headless-integration-tests-worker-01-20260925-0246"
branch_slug: "ralph-headless-integration-tests-worker-01-20260925-0246"
iteration: 1
status: IN_PROGRESS
started_at_utc: "2026-09-25T02:58:54Z"
updated_at_utc: "2026-09-25T03:33:14Z"
base_origin_main_sha: "0736add11eae7b7f745d7b7bf9806c116d72eed6"
rebased_onto_origin_main_sha: null
implementation_commit_sha: null
pull_request:
  status: PENDING
  number: null
  url: null
merge_actor_worker_id: null
decision_record_path: "docs/decisions/ralph-headless-integration-tests-worker-01-20260925-0246/agents/worker-01/pr-pending.md"
decision_index_path: "docs/decisions/ralph-headless-integration-tests-worker-01-20260925-0246/README.md"
merge:
  status: PENDING
  sha: null
  verified_remote_ref: "refs/heads/main"
  verified_origin_main_sha: null
  verification_method: null
  verified_at_utc: null
checks:
  - command: "PYTHONDONTWRITEBYTECODE=1 python3 tests/test_headless_test_pipeline.py"
    result: PASS
  - command: "bash -n scripts/run_headless_tests.sh"
    result: PASS
  - command: "SCLANG=.runtime/mount/SuperCollider.app/Contents/MacOS/sclang SCSYNTH=.runtime/mount/SuperCollider.app/Contents/Resources/scsynth bash scripts/run_headless_tests.sh"
    result: PASS
  - command: "env -u SCLANG -u SCSYNTH PATH=\"$PWD/.runtime/bin:$PATH\" bash scripts/run_headless_tests.sh"
    result: PASS
  - command: "git diff --cached --check"
    result: PASS
  - command: "ruby -e 'require \"yaml\"; YAML.load_file(\".github/workflows/headless-tests.yml\"); puts \"YAML syntax: OK\"'"
    result: PASS
  - command: "GitHub-hosted headless-tests workflow execution"
    result: NOT_RUN
blockers: []
next_action: "Finish staged-diff review, publish the branch and open a PR; then report AWAITING_MERGE and wait for coordinator authorization."
worker_sign_off:
  status: PENDING
  attestation_kind: null
  cryptographic_signature_status: NOT_CRYPTOGRAPHICALLY_SIGNED
  attested_at_utc: null
  statement: null
commit_signature_verification:
  status: NOT_CRYPTOGRAPHICALLY_SIGNED
  verifier: null
  evidence: null
  verified_at_utc: null
```
