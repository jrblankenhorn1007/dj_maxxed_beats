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
- [Copilot CLI Ralph runner](../scripts/ralph-loop.sh)
- [TDD skill](../.github/skills/tdd/SKILL.md)
- [Visual application test plan](./VISUAL_TEST_PLAN.md)
- [Decision log](./decision_log.md)
- [Current implementation status](./implementation_status.md)
- [Sound-design palette](./plugin/SOUND_DESIGN.md)

Project-facing documentation is organized under `docs/`, with plugin design
notes under `docs/plugin/`. The root `README.md` is a short repository landing
page. The `LICENSE` and `.github/skills/tdd/SKILL.md` stay at the repository
root/canonical Copilot skill path.

The development loop builds and tests the extension. The in-app music loop
generates and renders a limited set of musical variations; these are separate
loops.

## Running the development Ralph loop

Install and authenticate [GitHub Copilot CLI](https://docs.github.com/en/copilot/how-tos/copilot-cli/set-up-copilot-cli/install-copilot-cli).
Run the loop from the clean `main` worktree tracking `origin/main`, then check
the local prerequisites:

```bash
scripts/ralph-loop.sh --check
```

The runner pins Copilot CLI to **GPT-6 Luna** (`gpt-6-luna`) with `--model`;
it does not silently fall back if the model is unavailable to your account or
organization. It reads `RALPH_IMPLEMENTATION_PROMPT.md` once per
non-interactive iteration. For each pass, it creates a fresh
`ralph/iteration-<n>-<main-sha>` branch and a sibling worktree from the current
`main` tip. Copilot creates one implementation commit there; the runner stamps
its commit link and text-line counts into
[`implementation_status.md`](./implementation_status.md), then creates a
status-only commit. It pushes the iteration branch, merges it to `main`,
pushes `origin/main`, and verifies the remote tip before the next iteration.
Only after that verification does it remove the successful local worktree and
branch. The remote iteration branch remains for audit; both commits are also
reachable from `main`.

Iteration state is the committed repository files, not transient Copilot
conversation state: implementation, tests, `RALPH_PROGRESS.md`,
`implementation_status.md`, and `decision_log.md` are committed on the
iteration branch and merged/pushed to `main` each pass. If the loop is
interrupted before a merge, it preserves the active iteration worktree and
branch for review. Inspect them before restarting:

```bash
git worktree list
git -C <iteration-worktree-path> status --short
git -C <main-worktree-path> status --short
git -C <main-worktree-path> rev-parse main '@{u}'
```

Do not discard interrupted changes or blindly restart. Reconcile any
local-only commits and status updates; `--auto` requires a clean main worktree
whose `HEAD` exactly matches `origin/main`. It refuses to overwrite a leftover
iteration branch/worktree. Detailed test evidence remains in
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
Review the prompt and run only in a trusted environment. Each pass must
successfully push its iteration branch, merge it into `main`, and verify
`origin/main` before proceeding. A failed iteration is preserved for manual
recovery; successful local iteration worktrees and branches are removed after
the merge. The runner stops on an out-of-sync main branch, push/merge failure,
the prompt's `RALPH_COMPLETE` or `RALPH_BLOCKED` marker, or an invalid
iteration. Each pass can consume Copilot usage. Review the final changes and
tests yourself; a model's completion marker is not independent proof that
every requirement is met.

When migrating an existing single-branch Ralph worktree, stop its runner,
preserve and commit any pending work, push that legacy branch, merge it into
`main`, push `origin/main`, then remove only that verified, clean worktree and
its local branch. Start the new per-iteration loop from the clean main
worktree; do not try to run it from a legacy feature branch.

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
- [Copilot CLI reference](https://docs.github.com/en/copilot/reference/copilot-cli-reference/cli-programmatic-reference)
- [Supported Copilot models](https://docs.github.com/en/copilot/reference/ai-models/supported-models)
- [GPT-6 Luna availability](https://github.blog/changelog/2026-09-22-openais-gpt-6-sol-and-gpt-6-luna-now-available/)
- [Test-Driven Development: Red-Green-Refactor](https://martinfowler.com/bliki/TestDrivenDevelopment.html)
