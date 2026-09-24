# Ralph Implementation Prompt

This file is a compatibility pointer for the legacy shell runner, not a
standalone development prompt. The canonical TDD/Ralph guidance is maintained
in the [`copilot_skills` repository](https://github.com/jrblankenhorn1007/copilot_skills):

- [TDD and Ralph development skill](https://github.com/jrblankenhorn1007/copilot_skills/blob/main/.github/skills/tdd-ralph-loop/SKILL.md)
- [Ralph Loop agent](https://github.com/jrblankenhorn1007/copilot_skills/blob/main/.github/agents/ralph-loop.agent.md)
- [Ralph reference and project prompt](https://github.com/jrblankenhorn1007/copilot_skills/blob/main/.github/skills/tdd-ralph-loop/references/ralph-loop.md)

Use the local [implementation plan](./IMPLEMENTATION_PLAN.md) for product
acceptance criteria and [visual test plan](./VISUAL_TEST_PLAN.md) for GUI
verification. Keep project progress, status, and decisions in their existing
local files; do not copy shared TDD/Ralph workflow instructions here.

The legacy `scripts/ralph-loop.sh` reads this file but does not fetch or verify
the canonical skill and does not create isolated worktrees or merge iterations
to remote `main`. Do not run it with `--auto`; see the [README](./README.md).
