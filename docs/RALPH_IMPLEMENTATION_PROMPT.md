# Ralph Implementation Prompt

This file is a compatibility pointer read by the local Copilot CLI runner,
not a second source of general TDD or Ralph-loop instructions.

## Canonical workflow

Follow the shared
[Ralph Loop skill](https://github.com/jrblankenhorn1007/copilot_skills/blob/main/.github/skills/ralph-loop/SKILL.md)
for isolated iterations and verified remote integration. For behavior
changes, also follow the shared
[TDD skill](https://github.com/jrblankenhorn1007/copilot_skills/blob/main/.github/skills/tdd/SKILL.md)
and use the shared
[Ralph Loop agent](https://github.com/jrblankenhorn1007/copilot_skills/blob/main/.github/agents/ralph-loop.agent.md).

When an iteration implements or validates the SuperCollider music product,
consult the Ralph Loop skill's
[SuperCollider AI Music Agent prompt](https://github.com/jrblankenhorn1007/copilot_skills/blob/main/.github/skills/ralph-loop/references/ralph-loop.md)
for domain-specific context. Use it only when relevant; this project's
[implementation plan](./IMPLEMENTATION_PLAN.md) remains the source of product
acceptance criteria, and the local runner and status files remain authoritative
for project protocol.

The shared repository owns the general test-first and iteration workflow; do
not duplicate those instructions here.

## Project sources of truth

- [Product acceptance criteria](./IMPLEMENTATION_PLAN.md)
- [Visual verification](./VISUAL_TEST_PLAN.md)
- [Per-iteration evidence](./RALPH_PROGRESS.md)
- [Current project status](./implementation_status.md)
- [Append-only project decisions](./decision_log.md)

Keep project-specific progress, status, acceptance criteria, and decisions in
those files. Treat the upstream `supercollider/` checkout as read-only.

## Local runner protocol

The
[local runner](../scripts/ralph-loop.sh) invokes GPT-6 Luna for one iteration
in a fresh worktree and branch. It creates a status-report commit, publishes
the iteration branch, opens a pull request, and uses the repository-configured
GitHub merge process. It emits the final `RALPH_CONTINUE` or `RALPH_COMPLETE`
marker only after fetching `origin/main` and verifying the pull-request merge
commit there. Copilot's `RALPH_READY_CONTINUE` and
`RALPH_READY_COMPLETE` are pre-merge handoffs, not completion markers. If
remote integration is blocked, the runner records a blocked status on the
iteration branch when possible and emits `RALPH_BLOCKED`.

Before launching the agent, the runner fetches `origin`, verifies the clean
`main` integration worktree against the fetched `origin/main`, and includes
that preflight evidence in the iteration prompt. Treat it as satisfying the
shared agent's remote/worktree discovery requirement; do not repeat the fetch
or inspect the separate integration worktree.

The runner's `--auto` mode uses non-interactive `--allow-all-tools`; shell
commands can affect files outside the repository. It is not a sandbox. Run it
only in a trusted environment and review the resulting changes.
