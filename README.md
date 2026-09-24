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
- [Visual application test plan](./VISUAL_TEST_PLAN.md)
- [Decision log](./decision_log.md)
- [Current implementation status](./implementation_status.md)

The development loop builds and tests the extension. The in-app music loop
generates and renders a limited set of musical variations; these are separate
loops.

## Running the development Ralph loop

Install and authenticate [GitHub Copilot CLI](https://docs.github.com/en/copilot/how-tos/copilot-cli/set-up-copilot-cli/install-copilot-cli),
then check the local prerequisites:

```bash
scripts/ralph-loop.sh --check
```

## Required iteration integration

An iteration is not complete merely because its tests pass, its branch is
pushed, a pull request is open, or a local merge exists. Every iteration must
start from the latest `origin/main` in a fresh worktree and branch, commit its
implementation and any runner-owned status report there, then merge the
iteration's work into remote `origin/main` through the repository's configured
merge process. Fetch `origin` and verify that remote `main` contains the
merged work before advancing to another iteration or reporting a completion
marker.

The current `scripts/ralph-loop.sh` does not yet implement this lifecycle: it
runs in the checked-out branch, creates no iteration worktree/branch, and
pushes its commits directly to that branch. Do not use the legacy `--auto`
mode (`scripts/ralph-loop.sh --auto`) until the runner is updated to create an
isolated branch and verify each remote-main merge.
`scripts/ralph-loop.sh --check` only checks prerequisites; it does not verify
this integration requirement.

The TDD evidence remains in `RALPH_PROGRESS.md`; decisions remain in
`decision_log.md`. A compliant runner should rewrite
[`implementation_status.md`](./implementation_status.md) as a current-state
snapshot per iteration, not an append-only history, and keep runner-managed
status commits on the iteration branch until it is merged.

Each CLI iteration explicitly selects GPT-6 Luna (`--model gpt-6-luna`), rather
than inheriting the model of any parent agent. Availability depends on the
Copilot plan and organization model policies.

When the runner is updated, its non-interactive Copilot CLI execution uses
`--allow-all-tools`. This is not a sandbox: shell commands can affect files
outside the repository. The runner must not enable `--allow-all-paths`, and
the human launching it must use a trusted environment. Each pass can consume
Copilot usage. Review the final changes and tests yourself; a model's
completion marker is not independent proof that every requirement is met.

Validate the legacy runner's status-report workflow without making API calls;
this test does not cover worktree creation or remote-main merging:

```bash
bash tests/ralph-status-reporting.sh
```

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
