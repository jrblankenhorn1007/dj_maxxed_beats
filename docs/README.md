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
- [Development Ralph implementation prompt](./RALPH_IMPLEMENTATION_PROMPT.md)
- [Visual application test plan](./VISUAL_TEST_PLAN.md)
- [Decision log](./decision_log.md)
- [Current implementation status](./implementation_status.md)
- [Sound-design palette](./plugin/SOUND_DESIGN.md)

Project-facing documentation is organized under `docs/`, with plugin design
notes under `docs/plugin/`. The root `README.md` is a short repository landing
page. The [Ralph implementation prompt](./RALPH_IMPLEMENTATION_PROMPT.md) is
the project's entry point for shared-skill routing and the local development
workflow; consult it rather than duplicating those references here. `LICENSE`
remains at the repository root.

## Running the development Ralph loop

Start a development iteration by using this project's
[Ralph implementation prompt](./RALPH_IMPLEMENTATION_PROMPT.md) for current
shared-skill routing and agent configuration.

The shared workflow owns general development-loop mechanics; this project does
not provide a local shell runner. Product-specific acceptance criteria and
status sources remain in this repository: the
[implementation plan](./IMPLEMENTATION_PLAN.md),
[visual test plan](./VISUAL_TEST_PLAN.md),
[iteration progress](./RALPH_PROGRESS.md),
[current implementation status](./implementation_status.md), and
[append-only decision log](./decision_log.md). The development workflow is
separate from the in-SuperCollider music-variation feature.

## Product verification

Before declaring the product complete, follow the
[visual application test plan](./VISUAL_TEST_PLAN.md). A successful build,
headless test, log message, or mocked window is not visual confirmation; the
real SuperCollider application must be exercised with native screenshots on
the specified target platforms.
