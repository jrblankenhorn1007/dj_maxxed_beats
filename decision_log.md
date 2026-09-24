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
