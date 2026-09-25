# Branch decisions

- **Run/task:** `ralph-product-end-condition-20260925-015713-e03cb755` / `agent-instruction-contract`
- **Branch:** `ralph/agent-instructions-worker-02-20260925-015713-e03cb755`
- **Base:** `f9e1bb3edafff1cc6d24c640a8e0ed38f5bf49fe`
- **Worker:** `worker-02 / agent guidance`
- **Agent/PR record:** [worker-02 — PR pending](agents/worker-02/pr-pending.md)

## Decision

Version the four user-facing agent instruction files under `agent/` and
enforce their representative-request/safety contract with a local, deterministic
Python test rather than a live model call. The project plan names these files
and request categories but there is no provider-backed product workflow to
exercise yet. A text-contract test is repeatable and bill-free; it validates
that prompts keep the required guidance, not that a model follows it or emits
valid SuperCollider code.
