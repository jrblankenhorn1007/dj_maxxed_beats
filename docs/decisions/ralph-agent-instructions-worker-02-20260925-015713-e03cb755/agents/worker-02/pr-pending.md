# Worker-02 decision and PR record

- **Run/task:** `ralph-product-end-condition-20260925-015713-e03cb755` / `agent-instruction-contract`
- **Worker:** `worker-02 / agent guidance` (`runtime_agent_id: null`)
- **Iteration:** 1
- **Branch:** `ralph/agent-instructions-worker-02-20260925-015713-e03cb755`
- **Worktree:** `/Users/jrblankenhorn/dj_maxxed_beats.worktrees/ralph-agent-instructions-worker-02-20260925-015713-e03cb755`
- **Base `origin/main` SHA:** `f9e1bb3edafff1cc6d24c640a8e0ed38f5bf49fe`
- **Implementation commit SHA:** pending
- **PR:** pending publication and creation
- **Status:** `IN_PROGRESS`; merge authorization has not been requested or granted.

## Decision — deterministic instruction contract

- **Context:** The implementation plan requires four versioned agent instruction
  files and representative composition/editing requests. There is not yet an
  implemented provider or agent runtime to test model behavior.
- **Alternatives:** Make live/billable provider calls; defer tests until a
  provider runtime exists; or assert a deterministic contract over the
  versioned instructions without contacting a provider.
- **Rationale:** The local contract test can verify request coverage, review
  and approval safeguards, the existing verified ChaosOsc API statements,
  honest failure reporting, and no API-key-like literals without network
  access or real credentials.
- **Consequences:** Passing tests show that required instruction text is
  present and no matching key-like literal is committed. They do not prove
  model compliance, generated-code validity, rendering, or GUI behavior.

## Verification notes

- Test-first Red: `PYTHONDONTWRITEBYTECODE=1 python3 tests/test_agent_instructions.py`
  failed with 8 assertions because `agent/ROLE.md`, `agent/WORKFLOW.md`,
  `agent/SUPERCOLLIDER.md`, and `agent/SAFETY.md` were absent.
- Recovered intermediate mismatch: the first post-documentation
  `PYTHONDONTWRITEBYTECODE=1 python3 tests/test_agent_instructions.py` run
  failed 3 text assertions because Markdown line wrapping and singular/plural
  forms differed from the matcher. The matcher now normalizes whitespace and
  accepts singular/plural forms without weakening the safety requirements;
  the expanded 6-test contract passes.
- A later run of the same command failed one newly added review-order
  assertion because the workflow did not explicitly say approval followed the
  user's review of the exact diff. `WORKFLOW.md` now states that order; the
  final 6-test contract passes.
- No provider/API calls or credentials were used. SCIDE/GUI and cross-platform
  runtime validation are outside this documentation-focused increment.
