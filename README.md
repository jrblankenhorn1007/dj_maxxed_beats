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
- [Development Ralph-loop prompt](./RALPH_IMPLEMENTATION_PROMPT.md)
- [Copilot CLI Ralph runner](./scripts/ralph-loop.sh)
- [TDD skill](./.github/skills/tdd/SKILL.md)
- [Decision log](./decision_log.md)

The development loop builds and tests the extension. The in-app music loop
generates and renders a limited set of musical variations; these are separate
loops.

## Running the development Ralph loop

Install and authenticate [GitHub Copilot CLI](https://docs.github.com/en/copilot/how-tos/copilot-cli/set-up-copilot-cli/install-copilot-cli),
then check the local prerequisites:

```bash
scripts/ralph-loop.sh --check
```

The runner reads `RALPH_IMPLEMENTATION_PROMPT.md` on each pass and starts one
non-interactive Copilot CLI iteration at a time. There is no iteration-count
limit: it continues until Copilot reports verified completion or a blocker, a
real error occurs, or you stop it with Ctrl-C:

```bash
scripts/ralph-loop.sh --auto
```

`--auto` is an explicit opt-in: non-interactive Copilot CLI execution uses
`--allow-all-tools`. This is not a sandbox: Copilot can run shell commands
that affect files outside the repository. The runner does not enable
`--allow-all-paths`, but that flag alone would not contain shell commands.
Review the prompt and run only in a trusted environment. It requires a clean
working tree, one new commit per pass, and a successful push to `origin`; it
stops on the prompt's `RALPH_COMPLETE` or `RALPH_BLOCKED` marker or an invalid
iteration. Each pass can consume Copilot usage. Review the final changes and
tests yourself; a model's completion marker is not independent proof that
every requirement is met.

The in-SuperCollider music-variation loop is a product feature and is not
launched by this development runner.

Copilot CLI references:

- [Install Copilot CLI](https://docs.github.com/en/copilot/how-tos/copilot-cli/set-up-copilot-cli/install-copilot-cli)
- [Copilot CLI best practices](https://docs.github.com/en/copilot/how-tos/copilot-cli/cli-best-practices)
- [Test-Driven Development: Red-Green-Refactor](https://martinfowler.com/bliki/TestDrivenDevelopment.html)
