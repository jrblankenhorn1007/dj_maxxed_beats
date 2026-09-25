Ralph-Status: IN_PROGRESS

# Worker progress — agent instruction contract

## Iteration 1 — `agent-instruction-contract`

- **Run:** `ralph-product-end-condition-20260925-015713-e03cb755`
- **Worker:** `worker-02 / agent guidance` (`runtime_agent_id: null`)
- **Branch/worktree:** `ralph/agent-instructions-worker-02-20260925-015713-e03cb755` at `/Users/jrblankenhorn/dj_maxxed_beats.worktrees/ralph-agent-instructions-worker-02-20260925-015713-e03cb755`
- **Base:** `origin/main` `f9e1bb3edafff1cc6d24c640a8e0ed38f5bf49fe`; no rebase.
- **Scope:** Add the four versioned `agent/*.md` instructions and an offline representative-request contract test. No provider calls, credentials, GUI behavior, or application code are changed.

### Test-first evidence

- **Red:** Added `tests/test_agent_instructions.py` before the instruction files and ran `PYTHONDONTWRITEBYTECODE=1 python3 tests/test_agent_instructions.py`. It ran 5 tests and failed with 8 assertions because all four required `agent/*.md` files were absent. This was the missing instruction contract, not a test-runner or dependency failure.
- **Green:** After adding the four instruction files and making the contract's matching whitespace-insensitive, the same command passed all 5 initial tests.
- **Refactor:** Consolidated common text assertions, asserted behavior for each representative request, and added an offline check for API-key-like literals. An added review-order assertion prompted `WORKFLOW.md` to state explicitly that the user reviews the exact diff before approving it. Final `PYTHONDONTWRITEBYTECODE=1 python3 tests/test_agent_instructions.py` passed all 6 tests.
- **Reference check:** `PYTHONDONTWRITEBYTECODE=1 python3 tests/test_chaososc_language_contract.py` passed (2 tests), confirming the instruction's ChaosOsc constructor/API statements against the existing source contract.
- **Diff validation:** `git diff --cached --check` passed after staging the
  scoped change.

### Coverage and state

- The static contract covers a new sketch, tempo edit, instrumentation edit, error fix, code explanation, export, diff review, explicit approval before file changes/evaluation/rendering, truthful operation reports, and absence of API-key-like literals.
- These checks inspect Markdown only; they do not invoke a model/provider or establish that model responses produce valid compositions. SCIDE/GUI, provider, render, Windows 10 x64, actual MacBook Neo, and live-audition behavior are not exercised by this documentation-focused task.
- **Current state:** `IN_PROGRESS`; the scoped diff is staged and whitespace
  validation passes, but no implementation commit or PR has been recorded yet.
- **Next action:** Finish the diff and decision/status records, commit the scoped change, publish/open its PR if permitted, and wait for coordinator authorization before merging.
- **Memory:** Shared memory is coordinator-owned; post-merge review is pending coordinator verification.
