# dj_maxxed_beats

An AI-assisted procedural music and sound-design extension for SuperCollider.

## Direction

The product is designed to run from inside SuperCollider as a Quark/extension:

- An agent GUI opened from the SuperCollider IDE, with no separate
  user-facing desktop app.
- Custom C++ server UGens for distinctive sound design, controlled from
  SuperCollider language code.
- Procedural composition rendered to audio offline, with real-time audition
  available as an option.
- User-selectable OpenAI and Anthropic (Claude) providers and models.
- Per-request and per-session provider usage, estimated dollars, and
  informational, non-billable app credits (initially 100 credits per estimated
  USD).
- A user-started, bounded music-variation loop that preserves each candidate
  for audition and comparison.

This is the planned architecture, not a claim that those features are already
implemented. The initial approach avoids modifying or forking SuperCollider
core. A small headless provider helper may be included only if SuperCollider's
language environment cannot provide secure asynchronous API access.

## Project documents

- [Implementation plan](./IMPLEMENTATION_PLAN.md)
- [Canonical TDD and Ralph development skill](https://github.com/jrblankenhorn1007/copilot_skills/blob/main/.github/skills/tdd-ralph-loop/SKILL.md)
- [Ralph Loop agent](https://github.com/jrblankenhorn1007/copilot_skills/blob/main/.github/agents/ralph-loop.agent.md)
- [Copilot Skills repository](https://github.com/jrblankenhorn1007/copilot_skills)
- [Legacy runner prompt pointer](./RALPH_IMPLEMENTATION_PROMPT.md)
- [Legacy Copilot CLI Ralph runner](./scripts/ralph-loop.sh)
- [Visual application test plan](./VISUAL_TEST_PLAN.md)
- [Decision log](./decision_log.md)
- [Current implementation status](./implementation_status.md)

The development loop builds and tests the extension. The in-app music loop
generates and renders a limited set of musical variations; these are separate
loops. Shared TDD/Ralph instructions live in the
[`copilot_skills` repository](https://github.com/jrblankenhorn1007/copilot_skills);
this repository keeps the product plan and validation evidence.

## Development workflow

Use the canonical
[TDD and Ralph development skill](https://github.com/jrblankenhorn1007/copilot_skills/blob/main/.github/skills/tdd-ralph-loop/SKILL.md)
and its [Ralph Loop agent](https://github.com/jrblankenhorn1007/copilot_skills/blob/main/.github/agents/ralph-loop.agent.md).
The skill's references define the shared test-first and iteration workflow;
do not maintain another copy of those instructions here. Product acceptance
criteria remain in [the implementation plan](./IMPLEMENTATION_PLAN.md), and
the GUI sign-off checklist remains in
[the visual test plan](./VISUAL_TEST_PLAN.md).

## Legacy Copilot CLI runner

The local `scripts/ralph-loop.sh` is not compliant with the canonical
worktree/remote-main workflow: it operates in the checked-out branch, creates
no per-iteration worktree or branch, and does not merge and verify work on
remote `main`; `--auto` is unsupported until it is upgraded. Its `--check`
mode checks prerequisites only.

The runner currently selects GPT-6 Luna and invokes the CLI with
`--allow-all-tools`; automatic tool approval is not a sandbox, and shell
commands can affect files outside the repository. Each run can consume Copilot
usage.

`RALPH_IMPLEMENTATION_PROMPT.md` and `.github/skills/tdd/SKILL.md` are
compatibility pointers to the central skill, not independent instruction
sources. The existing status-report test covers only the legacy runner's
reporting behavior, not worktree creation or remote-main integration:

```bash
bash tests/ralph-status-reporting.sh
```

The legacy runner's CLI options are visible in
[`scripts/ralph-loop.sh`](./scripts/ralph-loop.sh). For Copilot CLI
installation and prerequisite checks, see
[GitHub's installation guide](https://docs.github.com/en/copilot/how-tos/copilot-cli/set-up-copilot-cli/install-copilot-cli)
and run `scripts/ralph-loop.sh --check` from a branch with a configured remote
upstream.

Before the development loop can report completion, it must also launch the
real SuperCollider GUI, run the visual scenario, capture and inspect native
screenshots on Windows 10 x64 and an actual MacBook Neo. See the
[visual application test plan](./VISUAL_TEST_PLAN.md); headless checks alone
are not sufficient.

The in-SuperCollider music-variation loop is a product feature and is not
launched by this development runner.

Copilot CLI references:

- [Install Copilot CLI](https://docs.github.com/en/copilot/how-tos/copilot-cli/set-up-copilot-cli/install-copilot-cli)
- [Copilot CLI best practices](https://docs.github.com/en/copilot/how-tos/copilot-cli/cli-best-practices)
- [Test-Driven Development: Red-Green-Refactor](https://martinfowler.com/bliki/TestDrivenDevelopment.html)
