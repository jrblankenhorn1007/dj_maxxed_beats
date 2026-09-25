# Ralph Implementation Prompt

This is the project's operational entry point for its shared-skill routing,
agent configuration, and project-specific source-of-truth files. Shared
workflow details remain in the canonical skills; product requirements and
project protocol remain in this repository.

## Relevant skills

- [Ralph Loop skill](https://github.com/jrblankenhorn1007/copilot_skills/blob/main/.github/skills/ralph-loop/SKILL.md) — **Always:** use for every Ralph iteration.
- [TDD skill](https://github.com/jrblankenhorn1007/copilot_skills/blob/main/.github/skills/tdd/SKILL.md) — **Behavior changes:** use test-first for behavior-changing implementation.
- [Project Memory skill](https://github.com/jrblankenhorn1007/copilot_skills/blob/main/.github/skills/project-memory/SKILL.md) — **Post-merge review:** review lessons after implementation content is merged and verified.
- [SuperCollider AI Music Agent prompt](https://github.com/jrblankenhorn1007/copilot_skills/blob/main/.github/skills/ralph-loop/references/ralph-loop.md) — **Only when the task concerns this SuperCollider music product:** use for domain-specific context.

## Shared agent configuration

The project uses the shared
[Ralph Loop agent](https://github.com/jrblankenhorn1007/copilot_skills/blob/main/.github/agents/ralph-loop.agent.md)
as agent configuration; this agent definition is not an additional skill.

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
