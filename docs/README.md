# Documentation index

The repository-root [README](../README.md) is the canonical project landing
page and describes the prototype's current state. This page indexes project
documentation rather than repeating the product overview.

## Product plan and verification

- [Implementation plan](./IMPLEMENTATION_PLAN.md) — product requirements,
  planned architecture, implementation phases, and acceptance criteria.
- [Visual test plan](./VISUAL_TEST_PLAN.md) — live SuperCollider/SCIDE
  scenarios and platform-specific visual sign-off requirements.
- [Current implementation status](./implementation_status.md) — implemented
  capabilities and verified or unverified coverage.
- [Progress evidence](./RALPH_PROGRESS.md) — chronological build, test, and
  runtime results for completed iterations.
- [Decision log](./decision_log.md) — append-only records of material product
  and architecture decisions.

## Branch evidence

- [Implementation archive](./implementation/README.md) — branch-by-branch
  index of implementation records, prompts, agent handoffs, decisions, and
  code-review folders.

## Development and sound design

- [Ralph implementation prompt](./RALPH_IMPLEMENTATION_PROMPT.md) — the
  project's shared development-workflow entry point and source-of-truth
  references.
- [Sound-design notes](./plugin/SOUND_DESIGN.md) — the ChaosOsc DSP
  prototype, controls, build state, and open verification gaps.
- [Headless test entrypoint](../scripts/run_headless_tests.sh) — runs the DSP
  tests and Python suite, including the plugin's SuperCollider NRT check. See
  the [root README](../README.md#run-the-developer-checks) for prerequisites
  and commands.

## Repository-root references

- [README](../README.md) — the canonical project overview, developer-check
  instructions, and current platform coverage.
- [LICENSE](../LICENSE) — the repository-root license text.
