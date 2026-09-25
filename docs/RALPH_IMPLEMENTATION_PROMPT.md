# Ralph Implementation Prompt

This is the project's operational entry point for its local Ralph runner,
shared-skill routing, and project-specific source-of-truth files. Shared
workflow details remain in the canonical skills; product requirements and
runner-specific protocol remain in this repository.

## Relevant skills

- [Ralph Loop skill](https://github.com/jrblankenhorn1007/copilot_skills/blob/main/.github/skills/ralph-loop/SKILL.md) — **Always:** use for every Ralph iteration.
- [TDD skill](https://github.com/jrblankenhorn1007/copilot_skills/blob/main/.github/skills/tdd/SKILL.md) — **Behavior changes:** use test-first for behavior-changing implementation.
- [Project Memory skill](https://github.com/jrblankenhorn1007/copilot_skills/blob/main/.github/skills/project-memory/SKILL.md) — **Post-merge review:** review lessons after implementation content is merged and verified.
- [SuperCollider AI Music Agent prompt](https://github.com/jrblankenhorn1007/copilot_skills/blob/main/.github/skills/ralph-loop/references/ralph-loop.md) — **Only when the task concerns this SuperCollider music product:** use for domain-specific context.

## Shared agent configuration

The local runner selects the shared
[Ralph Loop agent](https://github.com/jrblankenhorn1007/copilot_skills/blob/main/.github/agents/ralph-loop.agent.md)
as its agent configuration; this agent definition is not an additional skill.

This project's [implementation plan](./IMPLEMENTATION_PLAN.md) remains the
source of product acceptance criteria, and the local runner and status files
remain authoritative for project protocol.

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
