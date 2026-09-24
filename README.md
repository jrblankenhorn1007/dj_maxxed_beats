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

The runner reads `RALPH_IMPLEMENTATION_PROMPT.md` on each pass and starts one
non-interactive Copilot CLI iteration at a time. Each pass rewrites
[`implementation_status.md`](./implementation_status.md) as a current-state
snapshot, not an append-only history. Copilot creates one implementation
commit; after validating it, the runner stamps that commit's link and text-line
additions/deletions into the snapshot, creates a status-only commit, and pushes
both commits. That push moves the branch to the status commit, whose parent is
the implementation commit. Before starting, the runner requires a clean
worktree and exact equality between local `HEAD` and `origin/<branch>`. After
each push it verifies that the remote ref equals the new status commit and
prints the implementation and status commit IDs. It does not launch the next
Copilot iteration until that remote check succeeds.

Iteration state is the committed repository files, not transient Copilot
conversation state: implementation, tests, `RALPH_PROGRESS.md`,
`implementation_status.md`, and `decision_log.md` are committed and pushed
with each pass. If the loop is interrupted, inspect the worktree and branch
before restarting:

```bash
git status --short
git log --oneline '@{u}..HEAD'
git rev-parse HEAD '@{u}'
```

Do not discard interrupted changes or blindly restart. Review and preserve
uncommitted work, and reconcile any local-only commits with the remote and
status snapshot. `--auto` refuses to start while the worktree is dirty or when
local `HEAD` differs from `origin/<branch>`. Detailed test evidence remains in
`RALPH_PROGRESS.md`; decisions remain in `decision_log.md`.

There is no iteration-count limit: the runner continues until Copilot reports
verified completion or a blocker, a real error occurs, or you stop it with
Ctrl-C:

```bash
scripts/ralph-loop.sh --auto
```

`--auto` is an explicit opt-in: non-interactive Copilot CLI execution uses
`--allow-all-tools`. This is not a sandbox: Copilot can run shell commands
that affect files outside the repository. The runner does not enable
`--allow-all-paths`, but that flag alone would not contain shell commands.
Review the prompt and run only in a trusted environment. It requires a clean
working tree, one implementation commit plus the runner-generated status
commit per pass, and a successful, verified push of both to `origin` before
the next iteration. The runner stops on an out-of-sync branch, push failure,
the prompt's `RALPH_COMPLETE` or `RALPH_BLOCKED` marker, or an invalid
iteration. Each pass can consume Copilot usage. Review the final changes and
tests yourself; a model's completion marker is not independent proof that
every requirement is met.

Validate the runner's status-report workflow without making API calls:

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
