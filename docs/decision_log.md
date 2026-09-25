# Decision Log

This append-only decision record lives in `docs/decision_log.md`.

Append dated entries for material decisions. Do not edit old entries; supersede
them with a new entry that links back to the decision being replaced. Keep
credentials and private user data out of this file.

## 2026-09-24

### DEC-001 — Build an independent SuperCollider extension, not a core fork

- **Context:** The product needs to feel integrated with SuperCollider and
  include custom C++ audio functionality.
- **Decision:** Package the first release as a Quark/extension with an
  in-SuperCollider GUI, sclang classes/help, and C++ server plugin artifacts.
  Open its GUI from SCIDE through a simple class entry point; do not fork or
  patch SuperCollider core for the initial release.
- **Alternatives:** A standalone companion-app GUI or a fork with a docked
  SCIDE panel.
- **Rationale:** Quarks/extensions already package language classes, help, and
  server plugins. This keeps installation and maintenance small while avoiding
  a separate UI application and an upstream fork.
- **Consequences:** A Quark GUI window is the initial integration surface, not
  a docked IDE panel. A headless provider helper is allowed only if sclang
  cannot meet secure asynchronous HTTPS and credential-store needs.

### DEC-002 — Keep composition and synthesis in SuperCollider

- **Context:** The core feature is procedural track and sound-design creation.
- **Decision:** Generate/edit `.scd` compositions in sclang, use custom C++
  UGens for the distinctive DSP palette, and render prepared scores to WAV
  through scsynth NRT. Live audition is optional.
- **Alternatives:** Put agent/model logic into the audio plugin or require all
  audio to be generated in real time.
- **Rationale:** Server UGens run in the audio processing context and must not
  perform network, blocking, or project-file operations. NRT rendering supports
  programmatic tracks without requiring a live audio device.
- **Consequences:** The model and project workflow live outside the UGen
  callback. The initial UGen palette remains a deliberate discovery task.

### DEC-003 — Separate development and in-app music loops

- **Context:** The project uses an outer Ralph loop to build software and an
  in-product loop to explore musical variations.
- **Decision:** Keep these as separate systems. The Copilot CLI development
  runner has no iteration-count limit and stops on completion, a blocker, an
  operational error, or manual interruption. The in-app loop is user-started,
  limited to four candidate variations by default, stoppable, and never
  overwrites the source project without confirmation.
- **Alternatives:** Reuse one loop for both software changes and music
  generation, or run candidate generation indefinitely.
- **Rationale:** Software iteration and creative variation have different
  state, safety, and completion conditions.
- **Consequences:** The development prompt/runner never alters runtime music
  behavior; the in-app loop never edits application or plugin source.

### DEC-004 — Support OpenAI and Anthropic with explicit model selection

- **Context:** Users requested both Claude and OpenAI credentials and model
  choice.
- **Decision:** Provide independent OpenAI and Anthropic API-key settings,
  provider adapters, and refreshable model lists. Persist model selection per
  provider and never silently substitute a provider/model.
- **Alternatives:** Hard-code a single provider/model or require both keys.
- **Rationale:** Users may have access to different models/providers, and
  provider-specific APIs and capabilities differ.
- **Consequences:** Tests must cover each adapter and model-discovery failure
  without live API calls or credentials.

### DEC-005 — Display estimated dollars and informational usage credits

- **Context:** Users want to see usage in both credits and dollars.
- **Decision:** Display provider-reported token usage, estimated USD using
  versioned provider/model rates, and internal non-purchasable credits at an
  initial rate of 100 credits per estimated USD.
- **Alternatives:** Call credits a provider balance or show estimates as exact
  bills.
- **Rationale:** OpenAI and Anthropic do not share one provider-issued credit
  balance. An explicitly app-defined unit provides a comparable display while
  avoiding a claim about actual invoices.
- **Consequences:** Rates need a source/date and tests. Unknown or stale
  pricing is shown as unavailable/stale, not zero. Revisit the credit
  conversion before adding payment or subscriptions.

### DEC-006 — Use Red-Green-Refactor for implementation

- **Context:** The implementation spans DSP, provider APIs, safety-sensitive
  file operations, and an iterative generation loop.
- **Decision:** Apply test-first TDD to every behavior change: demonstrate Red,
  implement the smallest Green change, then refactor with tests passing. Keep
  the reusable process in `.github/skills/tdd/SKILL.md`.
- **Alternatives:** Add tests after implementation or use only manual
  end-to-end checks.
- **Rationale:** Tests written first clarify observable behavior and provide
  evidence that the test actually detects the missing behavior.
- **Consequences:** Each implementation iteration records Red/Green/refactor
  commands and outcomes in `RALPH_PROGRESS.md`; subjective listening
  complements, but does not replace, deterministic tests.

### DEC-007 — Commit and push each Copilot CLI iteration

- **Context:** The project is being implemented in the public
  `jrblankenhorn1007/dj_maxxed_beats` repository.
- **Decision:** The Copilot CLI runner invokes one prompt iteration at a time,
  requires exactly one direct-child commit with progress/decision updates,
  validates a clean tree, then pushes the branch. It uses non-interactive
  `--allow-all-tools` only through an explicit `--auto` opt-in and does not set
  `--allow-all-paths`.
- **Alternatives:** Manually batch multiple iterations into one commit or use
  an unbounded shell command with no completion protocol.
- **Rationale:** Per-iteration history is reviewable and push errors are
  surfaced. Exact status markers and operational errors stop the runner.
- **Consequences:** Automatic tool approval is not a sandbox; shell commands
  may affect paths outside the repository. Review the prompt and run only in a
  trusted environment. The user may stop the no-count-cap loop with Ctrl-C.

### DEC-008 — Maintain a rewritten implementation-status snapshot per iteration

- **Context:** The implementation loop needs an at-a-glance view of current
  feature state, verification, platform coverage, and blockers, with a
  verifiable link and line-count summary for each completed iteration.
  Supersedes DEC-007's single-commit-per-iteration detail.
- **Decision:** Maintain `implementation_status.md` as a current-state
  snapshot rewritten in place on every implementation iteration. Copilot
  commits the implementation and updated snapshot; the loop runner then stamps
  the implementation commit link and Git numstat totals and creates a
  status-only follow-up commit.
- **Alternatives:** Append status entries indefinitely, or ask Copilot to
  include the hash and LOC of a commit in the same commit that contains the
  status file.
- **Rationale:** A snapshot remains concise and reflects the latest project
  state. A commit cannot contain its own final SHA in one of its files, so a
  runner-generated follow-up commit can accurately reference the already
  created implementation commit and its line counts.
- **Consequences:** Each loop pass produces one implementation commit plus
  one runner-generated status commit; both are pushed together. The report
  counts added/deleted text lines, including documentation, and excludes
  binary changes.

### DEC-009 — Require visual end-to-end sign-off for the real application

- **Context:** Headless tests and successful builds cannot show that the
  integrated SuperCollider GUI launches, lays out correctly, and supports the
  user's actual workflow.
- **Decision:** Make live SCIDE launch, deterministic end-to-end interaction,
  native screenshot capture, and visual image inspection a required final
  gate on Windows 10 x64 and an actual MacBook Neo. Use a mock provider and a
  safe fixture so validation needs no real API credentials or billable calls.
- **Alternatives:** Treat unit/integration tests or screenshots of a mock
  window as sufficient, or expose a permanent network control API in the app.
- **Rationale:** Only a real visible run can catch integration, layout, and
  rendering problems. Existing accessibility automation should be tried
  first; if insufficient, a narrowly scoped test-only CLI/in-process driver
  can control the actual application without adding user-facing UI.
- **Consequences:** GUI-affecting iterations include visual evidence when
  available; completion requires both target-platform runs and screenshot
  artifacts. Any necessary IPC is opt-in test-only, authenticated,
  loopback-restricted, command-limited, and disabled in release builds.
  Missing GUI/device/screen-capture access remains an explicit blocker rather
  than a claimed pass.

### DEC-010 — Initial sound-design palette: ChaosOsc (logistic-map chaotic oscillator)

- **Context:** Phase 0/1 of the implementation plan require choosing and
  documenting the first custom C++ sound-design UGen before building the
  SuperCollider plugin wrapper. The development environment for this
  iteration has no `sclang`/`scsynth` or SuperCollider plugin build headers
  installed, so the plugin wrapper itself cannot yet be built or tested here.
- **Decision:** Select a logistic-map chaotic oscillator ("ChaosOsc") as the
  first palette entry, and implement it first as a dependency-free C++ DSP
  core (`plugin/ChaosOsc/Source/ChaosOscCore.hpp`) that is unit tested
  directly with a small assert-based C++ test (`plugin/ChaosOsc/Tests/`,
  run via `run_tests.sh`), independent of any SuperCollider toolchain. The
  planned controls (`chaosAmount`, `seed`, and a later decoupled update-rate
  control) are documented in `plugin/SOUND_DESIGN.md`. The SC `UGen`
  subclass, sclang class, and help file are deferred to a later iteration
  once a SuperCollider plugin build environment is verified/available.
- **Alternatives:** (a) Wait until a full SuperCollider plugin build
  environment is available before writing any DSP code — rejected because it
  blocks TDD progress on the one piece of the requirement that does not need
  that environment. (b) Pick a UGen backed by unbounded/unstable feedback
  (for example unconstrained analog-style feedback distortion) — rejected for
  the first entry because a chaotic map with a well-understood bounded
  parameter range is easier to make provably stable and testable first.
  (c) Use a physically-modeled or spectral technique for the first UGen —
  deferred as a possible later palette addition; the logistic map is simpler
  to specify, implement, and test end-to-end first.
- **Rationale:** The logistic map gives a distinctive, broadband, chaotic
  signal with a small, well-documented stable parameter range
  (`chaosAmount` clamped to `[3.57, 3.999]`), is trivially deterministic for a
  given seed (required both for reproducible tests and for reproducible
  candidate exploration later), and needs no allocation, I/O, or blocking
  calls, so it is real-time-audio-thread safe by construction. Building and
  testing its pure-math core first, independent of the SC toolchain,
  lets TDD proceed now and de-risks the DSP contract before wrapping it in
  `SC_PlugIn.h` boilerplate.
- **Consequences:** `plugin/ChaosOsc/Source/ChaosOscCore.hpp` is the
  authoritative DSP contract for ChaosOsc; the eventual `UGen` subclass must
  call it unchanged (only per-sample plumbing, control-rate parameter reads,
  and buffer I/O belong in the wrapper). Until a SuperCollider plugin build
  environment (source/headers, `sclang`, `scsynth`) is available in a
  development environment, the sclang class, help file, plugin build, NRT
  render, and real-time audition for ChaosOsc remain unimplemented and
  unverified; this is recorded as an explicit open task rather than an
  inferred pass.

### DEC-011 — Require verified Git synchronization before Ralph advances

- **Context:** An interrupted development loop can leave uncommitted work or
  a local-only implementation commit. Starting another iteration from that
  state risks confusing the project iteration number and leaves the previous
  work absent from the remote branch.
- **Decision:** Require a clean worktree and exact local `HEAD`/`origin/<branch>`
  equality before `--auto` starts. After each pass, push the implementation
  commit and its status-only follow-up together, verify that the remote ref
  equals the status commit, and report both commit IDs before continuing.
- **Alternatives:** Let the next model invocation proceed based only on the
  local status marker, or push the implementation commit separately before
  creating its status report.
- **Rationale:** The status report accurately records the completed commit
  hash and line counts, while the synchronization checks make the Git branch
  the durable record and prevent a restart from silently continuing on
  unpushed state.
- **Consequences:** A stopped run that leaves dirty or local-only work now
  fails preflight. Inspect and preserve that state, reconcile the commits and
  status snapshot, then restart from a clean branch whose remote tip matches.
  Copilot's completion/continue marker alone does not prove that a pass was
  committed or pushed.

### DEC-012 — Keep ChaosOsc's server wrapper thin and sample-accurate

- **Context:** The DSP core was tested independently, but its first C++
  SuperCollider wrapper needed a stable audio-rate control path without moving
  synthesis logic into blocking or allocating code.
- **Decision:** Wrap `ChaosOscCore` as an `SCUnit`, capture `seed` once when
  the UGen is constructed, and route each sample of the `chaosAmount` input
  through the core's `processBlock` helper.
- **Alternatives:** Read only the first control sample for a whole block, or
  duplicate the chaotic-map math inside the SuperCollider callback.
- **Rationale:** Reading the input buffer per sample preserves audio-rate
  modulation, while keeping the DSP arithmetic shared with the deterministic
  core tests and keeping the UGen callback free of I/O, allocation, and
  blocking work.
- **Consequences:** The C++ wrapper and exported plugin entry point compile
  against the pinned SuperCollider plugin API. Actual `scsynth` loading,
  sclang classes/help, NRT rendering, and real-time audition remain separate
  open verification tasks.

### DEC-013 — Isolate, merge, and clean up every Ralph iteration

- **Context:** The prior runner accumulated work on one feature branch and
  did not merge successful iteration results into `main`.
- **Decision:** Run the controller from a clean, synchronized `main`
  worktree. For each iteration, create a fresh branch and sibling worktree,
  let Copilot create one implementation commit, create the status-only
  follow-up commit, push that iteration branch, merge it into `main`, push
  and verify `origin/main`, then remove the successful local worktree and
  branch. Keep the remote iteration branch for audit. Preserve failed or
  interrupted worktrees for recovery.
- **Alternatives:** Continue one long-lived feature branch and merge only
  after the whole loop, or delete failed worktrees automatically.
- **Rationale:** Each verified increment reaches `main` promptly, while a
  separate worktree prevents in-progress edits from dirtying the controller's
  main checkout. Preserving failures avoids losing uncommitted work.
- **Consequences:** The runner must start from `main`; interrupted iteration
  work requires explicit reconciliation before another pass. The mocked
  workflow test verifies branch isolation, main merges/pushes, and cleanup.

### DEC-014 — Pin the development loop to GPT-6 Luna

- **Context:** The user requested GPT-6 Luna for the Copilot CLI Ralph loop.
- **Decision:** Invoke Copilot CLI with `--model gpt-6-luna` on every
  iteration and report the model in `--check`. Do not let the CLI choose
  automatically or silently substitute another model.
- **Alternatives:** Use Copilot's automatic model selection or a different
  model.
- **Rationale:** An explicit identifier makes the requested model choice
  reproducible and verifiable in tests and command output.
- **Consequences:** The authenticated Copilot account and organization must
  allow GPT-6 Luna; if it is unavailable, the CLI failure is surfaced rather
  than falling back.

### DEC-015 — Organize project documentation under `docs/`

- **Context:** Project plans, loop state, visual guidance, and plugin design
  notes were scattered at the repository root and under `plugin/`.
- **Decision:** Keep substantive project documentation under `docs/`, with
  plugin notes under `docs/plugin/`. Keep the root `README.md` as a concise
  repository landing page, and retain `LICENSE` and the TDD skill at their
  conventional/canonical paths.
- **Alternatives:** Leave the existing root layout or move every Markdown file,
  including the root README and Copilot skill.
- **Rationale:** A single documentation tree is easier to discover and keeps
  the GitHub landing page and Copilot's canonical skill discovery path intact.
- **Consequences:** The runner, prompts, tests, and internal links use `docs/`
  paths. Any future documentation moves must keep the runner's file paths and
  the Copilot skill location synchronized.

### DEC-016 — Complete each Ralph iteration through the configured remote merge

- **Context:** DEC-013 introduced per-iteration branches but used a local
  merge and direct push to `main`. The project requires the repository's
  configured remote merge process, including protected-branch checks or a
  merge queue when enabled. The incoming `main` branch also added this gate as
  DEC-010; DEC-016 preserves that requirement without reusing an existing
  decision number.
- **Decision:** After pushing an iteration branch, create a pull request and
  invoke `gh pr merge --auto` without forcing a merge strategy. Wait for GitHub
  to report the pull request merged, fetch `origin/main`, and verify that the
  reported PR merge commit is contained in remote main before emitting a final
  Ralph marker or starting another iteration. Use `RALPH_READY_CONTINUE` and
  `RALPH_READY_COMPLETE` as pre-merge handoff markers; only the runner emits
  `RALPH_CONTINUE` or `RALPH_COMPLETE` after verification.
- **Alternatives:** Merge locally and push directly, consider a pushed branch
  or open pull request complete, or force one merge strategy regardless of
  repository settings.
- **Rationale:** Only the remote merge process applies the repository's
  protections and configured merge policy. Verifying the PR merge commit also
  supports squash merges and merge queues without falsely requiring iteration
  commits to remain ancestors of `main`.
- **Consequences:** The runner requires an authenticated GitHub CLI, and its
  tests simulate a squash merge. If the PR is closed, merge processing times
  out, or remote verification fails, the runner records and verifies a BLOCKED
  status commit on the preserved iteration branch when possible, then emits
  only `RALPH_BLOCKED`.

### DEC-017 — Use shared Copilot Skills for TDD/Ralph guidance

- **Date:** 2026-09-24
- **Context:** This repository copied general TDD and Ralph-loop instructions
  into local skill and prompt files, creating a second source of truth beside
  the shared `jrblankenhorn1007/copilot_skills` repository.
- **Decision:** Treat the shared
  [TDD and Ralph development skill](https://github.com/jrblankenhorn1007/copilot_skills/blob/main/.github/skills/tdd-ralph-loop/SKILL.md)
  and [Ralph Loop agent](https://github.com/jrblankenhorn1007/copilot_skills/blob/main/.github/agents/ralph-loop.agent.md)
  as canonical. Keep `.github/skills/tdd/SKILL.md` and
  `docs/RALPH_IMPLEMENTATION_PROMPT.md` as concise redirect pointers. Retain
  product acceptance criteria, visual requirements, per-iteration evidence,
  status snapshots, and project decisions in this repository.
- **Alternatives:** Continue copying the shared workflow into local files, or
  remove local discovery points and require developers to find the shared
  repository themselves.
- **Rationale:** A single canonical workflow avoids drift while local pointers
  keep the shared instructions discoverable from this project.
- **Consequences:** Local skill and prompt files no longer duplicate TDD/Ralph
  procedures. The runner requires the canonical user-level Ralph agent and
  selects it by name. It remains a project-specific integration point and must
  continue to meet the shared fresh-worktree and verified-remote-merge
  requirements.

### DEC-018 — Request a supported PR merge method and retry pending checks

- **Date:** 2026-09-24
- **Context:** The repository does not have GitHub auto-merge enabled or a
  merge queue. A live `gh pr merge --auto` request failed because the
  non-interactive CLI requires an explicit method; a PR whose checks are still
  pending can also reject an early merge request.
- **Decision:** Supersede DEC-016's `--auto` invocation with
  `gh pr merge --merge`, consistent with this repository's prior merge-commit
  history and enabled settings. While the pull request remains open, retry a
  rejected merge request every 30 seconds and continue polling until merge
  verification succeeds or the configured timeout expires. Keep checking the
  GitHub-reported merge SHA on `origin/main` before advancing.
- **Alternatives:** Enable auto-merge administratively, use another allowed
  merge strategy, or treat the first rejected request as a blocker.
- **Rationale:** An explicit allowed merge method works with the current
  repository settings, while bounded retries accommodate checks that become
  satisfied after the initial request. Remote merge-SHA verification remains
  required regardless of the resulting merge topology.
- **Consequences:** The runner no longer depends on repository auto-merge
  configuration. Mocked lifecycle tests cover a pending first request followed
  by a successful retry, as well as merge-commit and squash-style remote merge
  results. A PR that remains open and unmergeable until timeout is recorded as
  BLOCKED and cannot advance the loop.

### DEC-019 — Let the runner own remote and integration-worktree preflight

- **Date:** 2026-09-24
- **Context:** During project iteration 3, the shared agent stopped before
  implementation because its non-interactive remote fetch and read-only check
  of the separate `main` worktree were denied. The runner had already checked
  the main worktree and remote tip, but that evidence was not available to the
  agent. No implementation changes or commit were made.
- **Decision:** Before each Copilot invocation, the runner checks that the
  integration worktree for `main` is unique and clean, fetches `origin`, and
  verifies local `main` matches the fetched `origin/main`. Include the
  integration path and verified commit in the prompt. Treat this as satisfying
  the shared agent's fetch/worktree-discovery step; the agent must work only
  in its iteration worktree and must not repeat the fetch or inspect the
  separate integration worktree.
- **Alternatives:** Grant the model broader interactive access to unrelated
  worktrees, remove the shared agent's safety checks, or allow implementation
  to proceed without fresh remote verification.
- **Rationale:** Runner-owned preflight is deterministic, uses the same
  repository context that creates and integrates iteration worktrees, and
  fails before invoking the model if freshness or cleanliness cannot be
  verified. Passing explicit evidence preserves the shared agent's safety
  requirements without requiring a second, potentially denied network call.
- **Consequences:** The lifecycle test starts with a stale remote-tracking ref
  and verifies that the runner refreshes it and passes the clean integration
  worktree details to Copilot. A live iteration rerun is required to confirm
  the shared agent accepts this preflight handoff.

### DEC-020 — Define deterministic fallbacks for NaN ChaosOsc inputs

- **Date:** 2026-09-24
- **Context:** The pure DSP core clamps finite out-of-range controls, but a
  NaN `chaosAmount` bypassed both comparisons and contaminated the oscillator
  state. A NaN `seed` likewise initialized the state to NaN, making every
  subsequent output invalid.
- **Decision:** Treat a NaN `chaosAmount` as the minimum documented map value
  (`3.57`) and a NaN `seed` as the default midpoint (`0.5`). Preserve the
  existing clamping behavior for finite controls and infinities.
- **Alternatives:** Allow NaN to propagate, reject it through an error channel
  unavailable to the audio callback, or change all non-finite values to the
  fallback.
- **Rationale:** Explicit deterministic fallbacks keep the real-time DSP
  callback simple and ensure malformed floating-point controls cannot poison
  oscillator state. Restricting the special case to NaN avoids changing
  established infinity handling.
- **Consequences:** Unit tests compare both fallbacks against their specified
  reference behavior. The sclang class, plugin loading, and NRT integration
  remain separate work requiring an installed SuperCollider toolchain.

### DEC-021 — Expose ChaosOsc through an audio-rate sclang class

- **Date:** 2026-09-24
- **Context:** The tested DSP core and compilable server-plugin wrapper had no
  matching language class or help entry, so compositions could not express
  the UGen through the normal SuperCollider graph-building API. This
  environment has neither `sclang` nor `scsynth`, and no available package
  installer was detected.
- **Decision:** Add `ChaosOsc.ar(chaosAmount = 3.9, seed = 0.5)` as a standard
  `UGen` class in the plugin's `Classes/` directory, with matching `HelpSource`
  documentation. Keep this slice limited to the audio-rate constructor and
  document that the seed is captured at Synth construction.
- **Alternatives:** Defer the class until a runtime can be installed, expose a
  control-rate constructor despite the server plugin's audio output, or add a
  runtime/NRT claim without executing SuperCollider.
- **Rationale:** The product requires a stable sclang-facing UGen interface;
  adding the conventional class/help source is a useful, independently
  reviewable increment. A source-contract test can verify the intended
  signature, while runtime behavior remains an explicit open check.
- **Consequences:** Source-level tests cover the class signature, defaults,
  controls, and help content. Loading the class and plugin, NRT rendering,
  and real-time audition still require a SuperCollider runtime and must not
  be treated as verified.

### DEC-022 — Match ChaosOsc's plugin API and control-rate handling to NRT runtime

- **Date:** 2026-09-24
- **Context:** The plugin headers pinned to development commit `ea52528`
  produced API version 7, while the official SuperCollider 3.14.1 release
  runtime expected API version 3, so `scsynth` refused to load the plugin.
  After aligning the API, deterministic NRT coverage also exposed that
  treating a control-rate `chaosAmount` buffer as an audio-rate sample array
  produced non-deterministic output.
- **Decision:** Use the official SuperCollider 3.14.1 release commit
  `426edf6d8742e1cc3bd85b51ca0c4e595d37a903` as the initial runtime/API
  compatibility target, cache its headers by revision, and have the plugin
  read audio-rate `chaosAmount` per sample while broadcasting scalar and
  control-rate values across the current block. Keep `seed` captured at UGen
  construction as documented in DEC-012 and DEC-021.
- **Alternatives:** Build a custom development runtime at `ea52528`; leave
  the mismatch and declare the stable 3.14.1 runtime unsupported; or assume
  every input is audio-rate and require compositions to avoid control-rate
  parameters.
- **Rationale:** Matching the plugin API to an official release prevents the
  server from rejecting the plugin. Respecting input rate avoids reading past
  a control-rate buffer and makes fixed-seed NRT output reproducible while
  preserving per-sample audio-rate modulation.
- **Consequences:** The release-pinned smoke build and NRT test verify
  loading, finite/non-silent output, determinism, construction-time seed
  behavior, and control-rate updates on macOS arm64 with SuperCollider
  3.14.1. Windows 10 x64, actual MacBook Neo, real-time audition, and other
  SuperCollider release ABIs remain unverified.
