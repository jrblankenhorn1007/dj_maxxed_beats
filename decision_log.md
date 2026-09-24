# Decision Log

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
