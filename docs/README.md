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
- [Canonical Ralph Loop agent](https://github.com/jrblankenhorn1007/copilot_skills/blob/main/.github/agents/ralph-loop.agent.md)
- [Copilot Skills repository](https://github.com/jrblankenhorn1007/copilot_skills)
- [Development Ralph-loop prompt](./RALPH_IMPLEMENTATION_PROMPT.md)
- [Copilot CLI Ralph runner](../scripts/ralph-loop.sh)
- [Local TDD skill pointer](../.github/skills/tdd/SKILL.md)
- [Visual application test plan](./VISUAL_TEST_PLAN.md)
- [Decision log](./decision_log.md)
- [Current implementation status](./implementation_status.md)
- [Sound-design palette](./plugin/SOUND_DESIGN.md)

Project-facing documentation is organized under `docs/`, with plugin design
notes under `docs/plugin/`. The root `README.md` is a short repository landing
page. The `LICENSE` and `.github/skills/tdd/SKILL.md` stay at the repository
root/canonical Copilot skill path. The local skill and prompt files point to
the shared `copilot_skills` repository; they do not duplicate its workflow
instructions.

The development loop builds and tests the extension. The in-app music loop
generates and renders a limited set of musical variations; these are separate
loops.

## Running the development Ralph loop

Install and authenticate [GitHub Copilot CLI](https://docs.github.com/en/copilot/how-tos/copilot-cli/set-up-copilot-cli/install-copilot-cli)
and [GitHub CLI](https://cli.github.com/). The GitHub CLI must be authenticated
for the repository that receives iteration pull requests. Install the
canonical `ralph-loop.agent.md` from the shared `copilot_skills` repository in
`$COPILOT_HOME/agents/` (default: `~/.copilot/agents/`). Run the loop from the
clean `main` worktree tracking `origin/main`, then check the local
prerequisites:

```bash
scripts/ralph-loop.sh --check
```

Follow the canonical
[TDD and Ralph development skill](https://github.com/jrblankenhorn1007/copilot_skills/blob/main/.github/skills/tdd-ralph-loop/SKILL.md)
and its [Ralph Loop agent](https://github.com/jrblankenhorn1007/copilot_skills/blob/main/.github/agents/ralph-loop.agent.md).
The local
[`RALPH_IMPLEMENTATION_PROMPT.md`](./RALPH_IMPLEMENTATION_PROMPT.md) is a
compatibility pointer to that shared workflow and this project's source-of-
truth files.

The runner pins Copilot CLI to **GPT-6 Luna** (`gpt-6-luna`) with `--model`;
it does not silently fall back if the model is unavailable to your account or
organization. It selects the shared `ralph-loop` agent with `--agent` and
reads the prompt pointer once per non-interactive iteration.
For each pass, it creates a fresh
`ralph/iteration-<n>-<main-sha>` branch and a sibling worktree from the current
`main` tip. Before each invocation, the runner fetches `origin`, verifies that
the clean `main` integration worktree matches the fetched `origin/main`, and
passes that evidence to the agent. The agent uses this runner-owned preflight
instead of repeating the fetch or inspecting another worktree. Copilot creates
one implementation commit there; the runner stamps its commit link and
text-line counts into
[`implementation_status.md`](./implementation_status.md), then creates a
status-only commit. It pushes the iteration branch, opens a pull request to
`main`, and requests a GitHub merge commit with `gh pr merge --merge`, matching
the project's prior merge-commit history. If a merge queue is required,
GitHub's queue controls the final merge. When branch requirements are pending,
the runner polls the PR and retries the merge request until it is merged or
the configured timeout expires. It then fetches `origin/main` and verifies the
reported PR merge commit is contained in that remote branch. Only after
verification does it fast-forward local `main`, remove the successful local
worktree and branch, and emit a final Ralph marker. The remote iteration
branch remains for audit; squash or queue merges may not retain the iteration
commits as ancestors of `main`.

### Required iteration integration

An iteration is not complete merely because its tests pass, its branch is
pushed, a pull request is open, or a local merge exists. Each iteration must
reach remote `origin/main` through the repository's configured merge process.
The runner waits for the remote pull request/merge queue to report merged and
checks that the reported merge commit is present on `origin/main` before
advancing or reporting `RALPH_CONTINUE`/`RALPH_COMPLETE`. If the GitHub CLI is
missing or unauthenticated, preflight fails before an iteration starts. If a
published PR is closed, times out, or cannot be verified, the runner records a
`Ralph-Status: BLOCKED` progress/status update on the iteration branch,
pushes and verifies that blocker commit when possible, preserves the
worktree/branch, and emits only `RALPH_BLOCKED`.
`scripts/ralph-loop.sh --check` verifies prerequisites only; it does not merge
an iteration. The runner retries a rejected merge request every 30 seconds while
the PR remains open. `RALPH_MERGE_TIMEOUT_SECONDS` can override the default
one-hour wait for required checks or merge-queue processing.

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
Review the prompt and run only in a trusted environment. A successful pass
must publish its branch, merge the PR through the configured GitHub process,
and verify `origin/main` before proceeding. The model emits a
`RALPH_READY_CONTINUE` or `RALPH_READY_COMPLETE` handoff; the runner withholds
the final `RALPH_CONTINUE` or `RALPH_COMPLETE` marker until the remote merge is
verified. A blocked, failed, or interrupted iteration is preserved for manual
recovery; successful local iteration worktrees and branches are removed after
the merge. Each pass can consume Copilot usage. Review the final changes and
tests yourself; a model's completion marker is not independent proof that
every requirement is met.

When migrating an existing single-branch Ralph worktree, stop its runner,
preserve and commit any pending work, push that legacy branch, open a pull
request, and merge it through the configured GitHub process. Verify the merge
on `origin/main`, then remove only that verified, clean worktree and its local
branch. Start the new per-iteration loop from the clean main worktree; do not
try to run it from a legacy feature branch.

Validate the runner's PR/merge workflow without making API calls; the test
simulates a pending-then-accepted merge request, merge-commit and squash-style
results, and a third closed-PR blocker:

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

CLI references:

- [Install Copilot CLI](https://docs.github.com/en/copilot/how-tos/copilot-cli/set-up-copilot-cli/install-copilot-cli)
- [GitHub CLI manual](https://cli.github.com/manual/)
- [Merge queue documentation](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/configuring-pull-request-merges/managing-a-merge-queue)
- [Copilot CLI best practices](https://docs.github.com/en/copilot/how-tos/copilot-cli/cli-best-practices)
- [Copilot CLI reference](https://docs.github.com/en/copilot/reference/copilot-cli-reference/cli-programmatic-reference)
- [Supported Copilot models](https://docs.github.com/en/copilot/reference/ai-models/supported-models)
- [GPT-6 Luna availability](https://github.blog/changelog/2026-09-22-openais-gpt-6-sol-and-gpt-6-luna-now-available/)
- [Test-Driven Development: Red-Green-Refactor](https://martinfowler.com/bliki/TestDrivenDevelopment.html)
