# worker-02 progress — AI workflow layer (ralph-ai-workflow-worker-02-20261007)

Scope: `extension/Classes/Workflow/**`, `agent/**`, workflow tests, and
`docs/design/workflow.md` per `docs/design/CONTRACT.md`.

## Delivered

- `MBProject` (confinement, `files/read/resolve`, `prepareEdit`, confirmed
  `apply` with backups and verified writes/rollback, safe `undo`), `MBEdit` +
  `MBDiff` (unified diffs).
- `MBAgent` (system prompt from the four `agent/*.md` files, selected context
  only, explicit model, meter usage, cancellable) and `MBResponseFormat`
  (strict `maxxedbeats.proposal/1`).
- `MBRenderer`/`MBRenderProcess`/`MBAudioCheck` (approved, isolated sclang
  Score build + scsynth NRT with ChaosOsc, unique outputs + sidecar, checks,
  progress, actionable errors, cancel/timeout).
- `MBVariationSession` (user-started, capped at 4 by default, fixed seeds,
  isolated candidates, stop early, confirmed apply, approved renders).
- `MBWorkflowJSON`, `MBWorkflowHandle`, `MBWorkflowTry` (sclang 3.14.1 `try`
  stack-corruption workaround).
- `agent/WORKFLOW.md` response format, `agent/SUPERCOLLIDER.md` renderable
  entry contract, `tests/test_agent_instructions.py` checks for both.

## TDD evidence

Each scenario was written first and failed (classes undefined), then passed:

- `tests/test_mb_workflow_project.py` (5 tests, 56 checks)
- `tests/test_mb_workflow_agent.py` (6 tests, 57 checks)
- `tests/test_mb_workflow_render.py` (7 tests; real ChaosOsc NRT renders)
- `tests/test_mb_workflow_variation.py` (6 tests; includes rendered candidates)

Notable Red→Green fixes: `files.includes` identity bug in a test; `try`
corruption found through missing checks and fixed with `MBWorkflowTry`;
runner continued after `1.exit` (restructured to one exit); determinism
compared the WAV `data` chunk (PEAK header chunk has a timestamp); exact
duration via an end marker one sample early.

## Gate

`SCLANG=… SCSYNTH=… bash scripts/run_headless_tests.sh` → quality checks passed; `Ran 124 tests in 229.8s, OK (skipped=1)`.

## Follow-ups for the coordinator

- Packaging must ship `agent/*.md` inside the Quark (`<quark>/agent`).
- GUI should pass `approveRenders: true` to `MBVariationSession.start` only
  after the user confirms rendering the candidates.
- Windows/Linux process launch is unverified.
