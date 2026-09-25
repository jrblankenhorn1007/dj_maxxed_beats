# Ralph Implementation Prompt

Use this project prompt with the shared **Ralph Loop** agent. Invoke the
canonical
[Ralph Loop agent](https://github.com/jrblankenhorn1007/copilot_skills/blob/main/.github/agents/ralph-loop.agent.md)
and follow the canonical
[Ralph Loop skill](https://github.com/jrblankenhorn1007/copilot_skills/blob/main/.github/skills/ralph-loop/SKILL.md)
for development-loop mechanics. The shared skill and agent are the sole
implementation of the outer development workflow; this project does not
provide or require a local shell runner.

For behavior-changing work, also follow the shared
[TDD skill](https://github.com/jrblankenhorn1007/copilot_skills/blob/main/.github/skills/tdd/SKILL.md).
When the task concerns the SuperCollider music product, consult the shared
[SuperCollider AI Music Agent prompt](https://github.com/jrblankenhorn1007/copilot_skills/blob/main/.github/skills/ralph-loop/references/ralph-loop.md)
for relevant domain context.

## Project sources of truth

The shared workflow does not replace project-specific acceptance criteria or
state. Read and preserve these project sources:

- [Product acceptance criteria and implementation plan](./IMPLEMENTATION_PLAN.md)
- [Visual application verification](./VISUAL_TEST_PLAN.md)
- [Append-only implementation evidence](./RALPH_PROGRESS.md)
- [Current product status](./implementation_status.md)
- [Append-only project decisions](./decision_log.md)

Use the shared skill's branch-scoped worker status and progress records for
Ralph run state; the coordinator owns the aggregate dashboard. Do not copy the
general Ralph or TDD implementation into this project. Treat the upstream
`supercollider/` checkout as read-only.

The development Ralph loop changes and verifies product code. The separate
in-SuperCollider music-variation feature runs only when a user starts it and
must remain bounded, stoppable, and isolated from the original project.
Workflow-maintenance work does not by itself advance the product
implementation iteration counter.
