# Ralph Implementation Prompt

This is the project's operational entry point for its shared-skill routing,
agent configuration, and project-specific source-of-truth files. Shared
workflow details remain in the canonical skills; product requirements and
project protocol remain in this repository.

## Relevant skills

- [Ralph Loop skill](https://github.com/jrblankenhorn1007/copilot_skills/blob/main/.github/skills/ralph-loop/SKILL.md) — **Always:** use for every Ralph iteration.
- [TDD skill](https://github.com/jrblankenhorn1007/copilot_skills/blob/main/.github/skills/tdd/SKILL.md) — **Behavior changes:** use test-first for behavior-changing implementation.
- [Project Memory skill](https://github.com/jrblankenhorn1007/copilot_skills/blob/main/.github/skills/project-memory/SKILL.md) — **Post-merge review:** review lessons after implementation content is merged and verified.
- [Ralph PR Review skill](https://github.com/jrblankenhorn1007/copilot_skills/blob/main/.github/skills/ralph-pr-review/SKILL.md) — **PR-backed branches:** use for independent pre-merge review and its evidence contract.
- [SuperCollider AI Music Agent prompt](https://github.com/jrblankenhorn1007/copilot_skills/blob/main/.github/skills/ralph-loop/references/ralph-loop.md) — **Only when the task concerns this SuperCollider music product:** use for domain-specific context.

## Shared agent configuration

The project uses the shared
[Ralph Loop agent](https://github.com/jrblankenhorn1007/copilot_skills/blob/main/.github/agents/ralph-loop.agent.md)
as agent configuration; this agent definition is not an additional skill.

For PR-backed Ralph work, use the configured read-only
[Ralph Code Reviewer](https://github.com/jrblankenhorn1007/copilot_skills/blob/main/.github/agents/ralph-code-reviewer.agent.md).
Also use the
[Ralph Security Reviewer](https://github.com/jrblankenhorn1007/copilot_skills/blob/main/.github/agents/ralph-security-reviewer.agent.md)
when the diff falls within its security-sensitive scope.

## Project sources of truth

The shared workflow does not replace project-specific acceptance criteria or
state. Read and preserve these project sources:

- [Product acceptance criteria and implementation plan](./IMPLEMENTATION_PLAN.md)
- [Visual application verification](./VISUAL_TEST_PLAN.md)
- [Append-only implementation evidence](./RALPH_PROGRESS.md)
- [Current product status](./implementation_status.md)
- [Append-only project decisions](./decision_log.md)
- [Per-branch implementation and review archive](./implementation/README.md)

## Branch-scoped implementation and review evidence

Create or update `docs/implementation/<branch-slug>/` for every development
branch, using the lowercased exact branch ref with each `/` replaced by `-`.
The branch dossier is the branch-centric entry point for:

- the exact task-specific user request and coordinator/worker/reviewer prompts
  under `prompts/`;
- dated agent handoffs and concise activity summaries under
  `agents/<stable-agent-id>/`;
- links to the shared skill's canonical branch-scoped status/progress records
  in `docs/ralph/<branch-slug>/` and append-only decisions in
  `docs/decisions/<branch-slug>/`; and
- a dedicated `code-review/` folder with the review state and each completed
  round's exact full base/head SHAs, reviewer roles, task-specific prompt,
  structured evidence-bounded report, and final author action/rationale.

Run one independent Ralph Code Reviewer for every PR-backed branch and add
the Ralph Security Reviewer for security-sensitive diffs. A round is bound to
one exact base/head pair. Complete at most two rounds: one initial review and,
when needed, one follow-up after the author acts on round one. After round two,
the author acts on that report alone; do not dispatch a third review. A
no-PR integration records `NOT_APPLICABLE` and does not launch a reviewer.
Follow the canonical PR Review skill for the full gate.

To avoid invalidating a review, do not commit a report to the audited PR branch
while the PR is open. Retain the report as sidecar evidence through the merge,
recheck the reviewed SHAs before authorization, and archive the report in the
branch dossier after integration. Preserve old artifacts at their canonical
paths and link them; do not duplicate or move their full histories. Mark
unavailable historical prompts/reports as `LEGACY_NOT_ARCHIVED`. Record actual
handoffs and concise outputs only: never store secrets, hidden
system/developer instructions, or private chain-of-thought, and do not
reconstruct missing transcripts.

Use the shared skill's branch-scoped worker status and progress records for
Ralph run state; the coordinator owns the aggregate dashboard. Do not copy the
general Ralph or TDD implementation into this project. Treat the upstream
`supercollider/` checkout as read-only.

The development Ralph loop changes and verifies product code. The separate
in-SuperCollider music-variation feature runs only when a user starts it and
must remain bounded, stoppable, and isolated from the original project.
Workflow-maintenance work does not by itself advance the product
implementation iteration counter.
