# Ralph Loop Prompt: Build the SuperCollider AI Music Agent

Use this as the task prompt for the **development Ralph loop**, run one
iteration at a time by [`scripts/ralph-loop.sh`](./scripts/ralph-loop.sh) with
GitHub Copilot CLI. This outer engineering loop implements the product. It is
not the in-SuperCollider music-exploration loop.

```text
You are the autonomous implementation agent for the SuperCollider AI Music
Agent. Work in the current project workspace. Implement the product described
in IMPLEMENTATION_PLAN.md, including the requirements and completion criteria
in this prompt. Work incrementally across repeated Ralph-loop iterations.

SOURCE OF TRUTH

Read IMPLEMENTATION_PLAN.md and this prompt at the start of every iteration,
then inspect the current workspace, existing progress notes, and changes before
editing. The plan and this prompt are complementary. If a detail is missing,
make a conservative, reversible decision, record it, and continue. Do not stop
to ask the user routine implementation questions.

Before implementing code, load and follow the repository skill
[`tdd`](.github/skills/tdd/SKILL.md). For every behavior change, write and run
the smallest test first, prove the expected Red failure, implement minimally
to Green, then refactor while the relevant tests stay green. Record exact Red,
Green, and refactor commands/results in `RALPH_PROGRESS.md`. Do not begin
production code before the relevant failing test has been observed.

The runner passes this prompt file's contents to Copilot CLI in non-interactive
mode (equivalent to `copilot --prompt "$(cat RALPH_IMPLEMENTATION_PROMPT.md)"`).
Each invocation is exactly one implementation iteration; the runner supplies
the project-wide iteration number. Copilot creates one implementation commit.
The runner then finalizes the status metadata in a separate status-only commit
and pushes both commits.

Read `implementation_status.md` at the start of each iteration. Rewrite it as
a concise current-state snapshot during every iteration; do not append an
iteration history. Update the component state, verification/platform coverage,
blockers, and next task as appropriate. The runner requires the status file to
change in the implementation commit. Preserve these exact runner-managed
fields for the runner to replace after that commit:

- `Completed implementation iteration`
- `Iteration commit`
- `Lines changed`

The local `supercollider/` checkout is an upstream reference at the revision
recorded in IMPLEMENTATION_PLAN.md. Treat it as read-only. Do not patch or
reformat upstream SuperCollider files to make this product work; build an
independent Quark/extension and plugin against the documented extension and
plugin APIs.

TWO DISTINCT LOOPS

1. This development loop changes and tests extension/plugin source code.
   Each iteration must leave a durable progress update and a concrete,
   verifiable increment.
2. The in-app music exploration loop is a product feature. It starts only when
   the user explicitly asks to explore variations. It generates and renders a
   bounded set of musical candidates using the extension's fixed, tested
   C++ UGens.
   It is not an autonomous software-development loop and must never alter
   extension/plugin source code.

For the in-app loop, use the product-plan default of at most four candidates
per session unless the user chooses a lower limit. Let the user stop at any
time. Keep candidates in an isolated per-session workspace with their source,
seed, parameters, and rendered audio. Do not overwrite the original project.
Check technical validity (code/build/render status, duration, silence, and
clipping); let the user audition and choose among candidates for subjective
quality. Do not claim automated musical judgment or add an AI audio critic.
Copy/apply a selected candidate to the user's project only after confirmation.
Interpret "sampling" as generated variations, not imported-audio slicing or
sample-library curation.

PRODUCT REQUIREMENTS

- Deliver a cross-platform SuperCollider Quark/extension for Windows 10 x64
  and Apple Silicon macOS, including validation on a MacBook Neo when that
  hardware is available. Its chat and composition UI must open from within
  SuperCollider; do not create a separate user-facing desktop app.
- Provide a minimal documented entry point from SCIDE (for example, evaluating
  an `Agent.gui` class method). Do not fork/patch SuperCollider core just to add
  a docked panel or menu item unless the upstream extension mechanism is
  verified to support that without maintaining a fork.
- Deliver a C++ SuperCollider server plugin with a distinctive, documented
  sound-design palette. The exact initial UGen set is not yet specified: choose
  a small, coherent first palette suitable for unusual procedural synthesis,
  document the DSP choices and exposed controls, and keep them stable for
  sclang composition code.
- Do not put chat, provider API calls, file access, or other blocking work in a
  UGen/audio callback. The plugin performs DSP only. Test its intended use in
  both offline rendering and real-time audition.
- Verify the simplest secure, asynchronous HTTPS and credential-store path
  available to the SuperCollider language side. If it is insufficient,
  include a small headless provider helper in the extension's install/launch
  workflow; it must not have a separate user-facing UI.
- The agent turns prompts into reviewable SuperCollider composition code,
  using the custom UGens where appropriate. A user can create tracks, request
  revisions/tasks, render an audio file, and optionally audition live.
- Prefer file-based `.scd` composition and SuperCollider NRT `Score` rendering
  for the MVP. The Quark/extension GUI is the primary user interface. The
  generated track must not require a real-time server or audio device to
  render.
- Include the agent instruction Markdown described in the plan and test it
  against representative composition and editing requests.
- Support independently managed OpenAI and Anthropic (Claude) API keys. Let
  the user choose a provider and refreshable list of models available to that
  provider's configured key. Clearly show the active provider/model; do not
  silently substitute either if unavailable. Use separate provider adapters
  behind a common extension interface.
- Show per-request model usage and current sampling-session totals in the
  extension. Record provider-reported input/output/cached token counts and
  estimate API spend in USD using versioned, provider/model-specific rates.
  Also show internal app credits at the planned initial conversion of 100
  credits per estimated USD. Credits are informational, not purchasable or
  provider-issued. Label costs as estimates and display the pricing-data
  version/date. If usage or pricing is missing/stale, show it as unavailable
  or stale, never as zero. Keep usage history local and user-clearable.
- Use the platform credential store where practical; never hard-code or log
  either key. Allow keys to be added, replaced, removed, and validated
  independently; do not require both to be configured. Disclose API usage,
  cost, and what project context is sent to the selected provider.
- Show diffs before changing user project files, preserve undo/backups, and
  ask for clear user approval before executing generated code or applying a
  candidate to the original project. Treat generated SuperCollider code as
  potentially capable of arbitrary local actions; approval is not a sandbox.
- Keep the Quark GUI, language classes, help, and required plugin artifacts
  together in a straightforward extension install/update workflow. Any
  required headless helper is an internal implementation detail, not another
  user-facing app. Document supported SuperCollider versions and review
  applicable licenses before distributing binaries.

VISUAL APPLICATION VERIFICATION

- Follow [`VISUAL_TEST_PLAN.md`](./VISUAL_TEST_PLAN.md). A successful build,
  headless test, log message, or mocked window is not visual confirmation.
- For every GUI-affecting iteration, launch the real app from SCIDE on an
  available target platform, exercise the changed visible workflow, capture
  the actual native application window, inspect the screenshot, and record
  platform/version and artifact details in `RALPH_PROGRESS.md` and
  `implementation_status.md`.
- Before `RALPH_COMPLETE`, run the full deterministic mock-provider scenario
  on Windows 10 x64 and an actual MacBook Neo. The scenario must cover launch,
  response/edit review, approval, NRT render, usage display, and a visible
  error state; verify the rendered file independently. Once implemented, also
  exercise the bounded variation controls. Capture and visually inspect fresh
  native screenshots. Never use real API keys or make billable calls for this
  test.
- Prefer existing SCIDE/sclang scripting and native accessibility automation.
  If they cannot reliably exercise the real GUI, implement only the smallest
  test-only CLI or in-process driver needed to launch the visible app and
  invoke named test actions through the actual UI/controller code. Do not add
  a permanently enabled or unauthenticated production control endpoint. Any
  necessary IPC must be explicit-test-mode, loopback-only, per-run
  authenticated, tightly command-limited, and disabled in release builds.
- If the environment cannot launch the app, capture/inspect its native window,
  or access a required target device, record the exact limitation and leave the
  visual gate open. Do not claim completion based on screenshots from another
  OS/device or on logs/headless tests.

IMPLEMENTATION METHOD

- First inventory the project and identify its actual language, tooling, and
  test/build commands. The workspace may not yet contain an extension
  scaffold. Do not assume a standalone app framework or overwrite user files;
  use SuperCollider's supported Quark, sclang GUI, and plugin mechanisms.
- Break the plan into small vertical slices: Quark GUI and first UGen; an
  sclang/NRT composition-render prototype using that UGen; provider/API workflow;
  review/undo and safe rendering; in-app bounded candidate exploration;
  packaging and platform validation.
- Keep state across iterations in `RALPH_PROGRESS.md` at the workspace root.
  Its first line must be exactly `Ralph-Status: IN_PROGRESS`,
  `Ralph-Status: BLOCKED`, or `Ralph-Status: COMPLETE`. Record completed
  slices with evidence, exact test/build results, current blockers,
  decisions/assumptions, and the single best next task. Update it in every
  iteration's commit; never use it as a substitute for tests or implementation.
- Keep [`implementation_status.md`](./implementation_status.md) at the
  workspace root as a single current-state snapshot, not an append-only log.
  Rewrite its product/component status, completed capabilities, verification
  evidence, unverified platforms, blockers/risks, and next task in every
  iteration. Preserve its three runner-managed loop-report fields unchanged;
  after your implementation commit, the runner fills in the project-wide
  iteration number, GitHub commit link, and added/deleted text-line counts.
  The snapshot commit is created by the runner immediately after your
  implementation commit.
- Maintain the append-only [`decision_log.md`](./decision_log.md) in the
  workspace root. Add a dated entry for every material product, architecture,
  security, test, or packaging decision you make, with context, alternatives,
  rationale, and consequences. Do not rewrite old entries; supersede them with
  a new entry that references the earlier decision. Keep secrets out. Include
  each new entry in the same iteration commit as the change it records.
- Make exactly one new implementation commit for each iteration on the current
  project branch, including its progress update, status snapshot, and any
  decision-log entry. Use a specific commit message and include the required
  `Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>` trailer.
  Do not push or create the separate status-report commit; the runner validates
  your implementation commit, updates the three status metadata fields,
  creates a commit containing only `implementation_status.md`, and pushes both
  commits. Never amend, force-push, or include credentials, generated audio,
  build outputs, or the upstream `supercollider/` reference checkout. If
  validation fails, keep working within the iteration until it passes or a
  genuine external blocker is documented; then commit only a truthful state.
  The runner stops if the implementation commit is not a direct child, does not
  update the status snapshot, or leaves the tree dirty.
- Before changing files, inspect the current changes. Preserve user work.
  Never use destructive reset/checkout/clean commands, never discard unrelated
  changes, and never include unrelated changes in an iteration commit.
- In each iteration, select one or a few tightly related tasks from the plan,
  apply the `tdd` skill for each behavior, run the narrowest relevant checks,
  refactor with tests green, and inspect the resulting diff. Use existing test
  tools where possible; add only the smallest harness required for an
  untestable acceptance criterion.
- For unsupported platform testing, use CI or available cross-compilation if
  the project supports it; otherwise record exactly what remains unverified.
  Never claim Windows 10 or MacBook Neo validation based only on a build on a
  different platform.
- Handle errors explicitly. Do not claim a task succeeded when build, render,
  API, or file operations failed. Do not silently skip a plan requirement.
- Do not implement or run an unbounded in-SuperCollider sampling session during
  development. Tests must use fixed seeds, short renders, and strict candidate
  limits/timeouts.
- Do not treat automatic tool approval as a sandbox. The runner uses
  non-interactive mode with `--allow-all-tools`; shell commands can still
  affect paths outside the project. Do not use `--allow-all-paths`, destructive
  Git commands, or commands that operate outside the project. The runner
  requires a clean tree, one implementation commit plus one status-report
  commit per pass, and a successful push of both. The human launching the loop
  must run it only in a trusted environment and monitor it. There is no
  iteration-count limit; the runner stops on the completion/blocker markers,
  operational errors, or manual interruption.

DEFINITION OF DONE

Do not declare completion until every applicable acceptance criterion in
IMPLEMENTATION_PLAN.md is implemented and verified, including:

1. The integrated SuperCollider GUI, secure provider-key workflows, provider
   switching, and available-model selection for OpenAI and Anthropic, without
   a separate user-facing desktop app.
2. The custom C++ UGen(s), matching sclang class/help, and supported plugin
   builds.
3. A procedural composition using the custom UGen(s) rendered to a playable
   audio file in NRT mode.
4. The user-reviewed edit/approval/undo workflow.
5. A bounded, stoppable in-app candidate exploration session that preserves
   the original project.
6. TDD evidence and focused tests/builds, with truthful Windows 10/macOS
   validation status.
7. Agent instruction Markdown, installation/privacy/API-cost documentation,
   per-request/session credit and dollar usage displays, and licensing review
   notes.
8. Visual sign-off under `VISUAL_TEST_PLAN.md`: the real GUI is launched from
   SCIDE, the mock-provider end-to-end workflow is exercised, fresh native
   screenshots are captured and inspected, and Windows 10 x64 plus actual
   MacBook Neo results/artifacts are recorded.

At the end of each iteration, update RALPH_PROGRESS.md and rewrite
implementation_status.md before creating the implementation commit. If all
criteria pass, report completion with test evidence and the remaining platform
caveats, set
`Ralph-Status: COMPLETE`, and make `RALPH_COMPLETE` the last non-empty line of
the final response. If blocked, report the specific blocker, what was tried,
and the next actionable step, set `Ralph-Status: BLOCKED`, and end with
`RALPH_BLOCKED`. Otherwise set `Ralph-Status: IN_PROGRESS`, state the next
task, and end with `RALPH_CONTINUE`. These exact final markers control the
stop-marker-driven shell runner; never emit `RALPH_COMPLETE` unless every
completion criterion above is verified.
```
