# SuperCollider AI Music Agent — Implementation Plan

## Goal

Build a cross-platform AI music assistant for SuperCollider. A user can describe
music they want, have the agent create a procedural composition, render it to an
audio file, and ask for revisions or other project tasks.

The initial target platforms are Windows 10 (64-bit) and the Apple Silicon
MacBook Neo. The assistant supports user-provided OpenAI and Anthropic (Claude)
API keys, and lets the user choose a provider and an available model.

## Recommended architecture

Make the user experience live inside SuperCollider, while keeping network
requests and DSP in the appropriate processes:

1. **SuperCollider extension (primary product):** an installable Quark provides
   the in-SuperCollider agent window, language classes, help, composition
   helpers, and platform-specific plugin binaries. The user opens it from the
   SuperCollider IDE; there is no separate user-facing companion app.
2. **C++ server plugin (core audio component):** supplies the distinctive
   sound-design UGens, exposed to sclang for procedural compositions. It
   performs DSP only, not chat or web requests.
3. **Provider/API bridge (implementation detail):** first check whether the
   supported SuperCollider language environment can make secure asynchronous
   HTTPS requests and use the platform credential stores. If it cannot, bundle
   a small headless helper with the extension to handle provider API calls and
   credentials. It has no separate user-facing UI and communicates locally
   with the SuperCollider language client.
4. **Composition/rendering:** `sclang` builds the composition and NRT `Score`;
   `scsynth` renders audio to a file. Live audition is optional.

Keep the extension self-contained from the user's point of view: one
SuperCollider installation workflow and one agent window. Do not fork or modify
SuperCollider core for the initial version. Launch the UI from the IDE through
a simple documented entry point (for example, an `Agent.gui` class method);
defer a docked IDE panel or core menu changes unless the upstream extension
surface is verified to support them without maintaining a core fork.

Custom C++ sound design is a core requirement. The first sound-design phase
will define a distinctive palette and choose the initial UGen(s); examples to
explore include chaotic or feedback-driven synthesis, unusual modulation, and
custom distortion or spectral processing. The agent should compose with a
stable, tested set of UGen controls rather than generate new C++ source for
each track. SuperCollider's *Writing Unit Generators* guide explains that
UGens run in the audio server's real-time context, where blocking calls are
unsafe. Therefore, model calls and project editing stay in the sclang-side
agent workflow or a headless provider helper; the UGen performs audio DSP only.
The same composition can be auditioned live or rendered offline.

## Proposed user workflow

1. From the SuperCollider IDE, the user opens the agent window and describes a
   track or selects an existing `.scd` project.
2. The user configures an OpenAI or Anthropic API key, selects that provider,
   and chooses an available model. The extension explains that prompts and
   selected project context are sent to that provider.
3. The agent proposes a musical plan (for example, sections, tempo, motifs,
   instruments, and duration) and generates or edits `.scd` composition code
   that can use the custom sound-design UGens.
4. The user reviews the plan and code changes, then approves a render.
5. `sclang` builds/runs the composition logic and produces a timed score;
   `scsynth` renders that score to WAV in NRT mode. This render can run faster
   or slower than real time and does not require an audio device.
6. The user listens to the result, asks for changes, and renders a new version.
   Real-time playback can be offered as an optional preview, not a requirement.

## Two separate Ralph loops

These are distinct features with different jobs:

1. **Development Ralph loop (outside SuperCollider):** repeatedly implements and
   verifies the product against this plan. Use the project's
   [Ralph implementation prompt](./RALPH_IMPLEMENTATION_PROMPT.md) for current
   shared-skill routing and local development-loop guidance rather than
   duplicating those references here. This plan remains the source of truth for
   the product's acceptance criteria; the development loop changes extension
   and plugin code, not music-generation behavior. This project does not
   provide a local shell runner for the development loop; headless product
   tests use the separate
   [headless test suite](../README.md#run-the-developer-checks).
2. **In-app music exploration loop:** when the user explicitly starts a
   sampling session, generate and render a bounded set of alternative musical
   candidates using the custom UGens. Keep each candidate and its settings
   separate, let the user audition/compare them, and let the user stop early.
   Initial default: up to four candidates per session. Automatically check
   build/render success, duration, silence, and clipping; use the user's
   listening and selection for subjective quality. Do not add an AI audio
   critic unless specified separately.

The in-app loop must never run without a user-started session or continue
indefinitely. Store candidates in a per-session workspace, preserve the
original project, and only apply a selected candidate to the project after
confirmation. Here, "sampling" means exploring generated music variations; it
does not mean slicing or classifying a user's imported audio samples.

Use the shared **Ralph Loop** agent with this project's
[Ralph implementation prompt](./RALPH_IMPLEMENTATION_PROMPT.md) to start the
development workflow. The shared skill and agent define the general iteration,
verification, and integration process. Project-specific acceptance criteria,
visual coverage, progress evidence, current implementation status, and
append-only decisions remain in this repository's
[`IMPLEMENTATION_PLAN.md`](./IMPLEMENTATION_PLAN.md),
[`VISUAL_TEST_PLAN.md`](./VISUAL_TEST_PLAN.md),
[`RALPH_PROGRESS.md`](./RALPH_PROGRESS.md),
[`implementation_status.md`](./implementation_status.md), and
[`decision_log.md`](./decision_log.md). The branch-centric index for their
implementation, prompt, handoff, decision, and code-review evidence is the
[`implementation/` archive](./implementation/README.md).

## Decision log

Maintain [`decision_log.md`](./decision_log.md) in `docs/` as an
append-only, dated record of material product, architecture, security, testing,
and packaging decisions. Each entry records context, alternatives, rationale,
and consequences. Commit each entry with the implementation or plan change it
explains; supersede old decisions with a new entry rather than rewriting
history. Never record credentials or private user data.

## Component responsibilities

### In-SuperCollider agent GUI

- This is an in-SuperCollider GUI, not a separate desktop app. Provide a small
  documented entry point to open it from SCIDE and a workflow that does not
  require editing SuperCollider core.
- Manage conversations and the selected project in the agent window.
- Send prompts and only the project context explicitly selected or needed for
  the task to the provider selected by the user.
- Provide provider adapters for OpenAI and Anthropic (Claude), with a common
  extension-facing interface for supported chat, streaming, and structured-edit
  capabilities. Keep provider-specific API behavior behind these adapters.
- Show usage after each model request and for the current sampling session:
  provider-reported input/output/cached token counts, estimated API cost in
  USD, and estimated app credits. Keep a local usage history that the user can
  inspect and clear.
- Define app credits as an internal, non-purchasable usage display, initially
  at 100 credits per estimated USD. This is not a provider balance, invoice, or
  promise of exact billing. Revisit the conversion before introducing paid app
  credits or subscriptions.
- Estimate USD from versioned, provider/model-specific input, output, and
  cached-token rates. Show the rate-table version/date and label totals as
  estimates. If usage or current pricing is unavailable, show what is known
  and label credits/USD as unavailable or stale; never report zero as a
  success-shaped fallback.
- Fetch and refresh each configured provider's available model list using its
  model-list API; show provider and model IDs clearly, and persist the selected
  model separately for each provider. Filter or label models according to
  capabilities the extension requires. Do not silently substitute a model if the
  selected model is unavailable.
- Produce reviewable composition/code changes, preserve backups/undo, and
  avoid modifying files outside the selected project.
- Start and monitor a render, report progress and actionable failures, and
  clearly identify the resulting audio file.
- Clearly report API, connection, parsing, and execution errors; do not present
  an unsuccessful action as completed.
- Keep provider/API details behind an interface so a provider or model can be
  changed without changing the SuperCollider integration.
- Keep HTTP work asynchronous and off the audio thread. If a headless helper is
  necessary, package/start/stop it as part of the extension so users do not
  install or operate a separate UI application.

### Provider and API-key handling

- Support separately managed OpenAI and Anthropic API keys. The user can add,
  replace, remove, or validate each key independently.
- Never hard-code keys or write them into project files, agent Markdown, logs,
  crash reports, or source control.
- Prefer the operating system's credential store (macOS Keychain and Windows
  Credential Manager). Do not require both providers to be configured.
- Redact secrets from diagnostic output and ensure errors do not echo request
  headers or token values.
- Explain that API usage may incur charges and that prompts/project context are
  transmitted to the selected provider.
- If a provider's model-list request fails, report the error and identify any
  cached model list as potentially stale. Never silently change the provider
  or model.
- Do not send telemetry or usage history outside the user's machine except as
  part of the model request the user initiated.

### SuperCollider Quark / language bridge

- Make the Quark/extension the primary user-facing integration. It includes
  the GUI, language classes, help, and the plugin artifacts needed for the
  supported platform. Prefer ordinary `.scd` project files for generated
  compositions.
- Verify the simplest secure, asynchronous provider-request path available to
  sclang. If a helper is necessary, keep it headless, bundled, and limited to
  model/key operations; use a minimal documented local IPC protocol.
- Use OSC only when it is a suitable part of the selected local communication
  design; do not add an extra bridge process without need.
- Bind to loopback only by default, validate message shape and size, and avoid
  accepting commands from arbitrary network peers.
- Code generation and offline rendering must not depend on a separate
  user-facing desktop application.
- Separate proposing code from evaluating code; require an explicit user
  approval before executing generated composition code or starting a render.

### C++ server plugin

- Treat custom sound-design UGens as a core audio feature. Define the initial
  sound palette and UGen behaviors before implementation; expose usable,
  documented parameters to sclang so the agent can build arrangements from
  them.
- Keep model calls, chat, file access, and project editing out of the UGen.
- Follow SuperCollider's plugin API, provide the matching sclang class and help
  documentation, and test against the supported `scsynth` server version.
- Build platform-specific artifacts and verify architecture/ABI compatibility.
  The server loads plugins at startup, so document installation and restart
  requirements.
- Validate rendering both offline and in real time. Add a `supernova` build
  only if it is an explicit product requirement; its threading behavior needs
  separate validation.

## Agent instruction Markdown

Keep user-experience instructions separate from code and executable project
content. Start with:

- `agent/ROLE.md` — identity, scope, and musical collaboration style.
- `agent/WORKFLOW.md` — clarify intent when useful; plan edits; show diffs;
  explain tradeoffs; request approval before applying or evaluating code.
- `agent/SUPERCOLLIDER.md` — supported SuperCollider patterns, project
  conventions, and verified API usage.
- `agent/SAFETY.md` — API-key/privacy rules, project boundaries, refusal to
  claim actions that failed, and safeguards for generated code.

Version these files with the app. Test them against representative requests
(new sketch, change tempo, alter instrumentation, fix an error, explain code,
and export-oriented tasks) so that changes to instructions do not silently
change important behavior.

## Implementation phases

### 0. Confirm the product boundary

- Identify the first supported SuperCollider release(s), project format, and
  the exact Quark entry point and supported way to open its GUI from SCIDE.
- Verify whether sclang can provide secure asynchronous HTTPS and OS
  credential-store access. Select the smallest supported implementation; only
  add a bundled headless helper if the language-side route is insufficient.
- Define the first render target (for example, stereo WAV, sample rate, and
  bit depth) and whether live preview is part of the MVP.
- Decide how generated arrangements are represented: direct `.scd` code,
  structured arrangement data translated to `.scd`, or both. Default: generated
  and reviewable `.scd` code.
- Define the first custom sound-design palette and the specific DSP behavior
  for each initial C++ UGen.
- Decide whether the MVP only renders offline or also controls a running
  `sclang` session. Default: file-based compositions and offline render.
- Turn the product acceptance criteria into a prioritized test list before
  implementation. Follow the shared test-first workflow routed from the
  project's [Ralph implementation prompt](./RALPH_IMPLEMENTATION_PROMPT.md);
  keep this plan focused on product-specific acceptance criteria and test
  coverage.

### 1. Validate the SuperCollider integration

- Validate the minimal C++ UGen API and its observable DSP contract with
  focused tests and short NRT renders, following the shared test-first process
  routed from the project's
  [Ralph implementation prompt](./RALPH_IMPLEMENTATION_PROMPT.md). Then
  implement its sclang class and help, use it in a procedural composition,
  convert that composition to a `Score`, and render a WAV using NRT mode.
- Install a minimal Quark/extension and open a small GUI from SCIDE without
  changing SuperCollider core.
- Verify the workflow does not need a running real-time server or audio device.
- Verify the custom UGen also works in a real-time audition.
- Prototype the provider-request path and local helper IPC only if required by
  the selected networking/credential implementation.
- Confirm where the extension is installed and how users restart/reload the
  language and server.
- Document exact supported SC versions and plugin binary compatibility.

### 2. Implement the safe agent workflow

- Add the in-SuperCollider agent window with prompt submission, the proposed
  musical plan, response streaming/status, provider/model selection, and
  secure key management.
- Generate a composition and reviewable file edits; validate paths remain
  under the selected project and show a diff before writing.
- Add backups/undo and clear handling for malformed responses, API errors,
  render failures, and rejected changes.
- Add explicit confirmation before evaluating generated code and generating
  audio.

### 3. Complete the integrated extension and core sound-design plugin

- Package the Quark GUI, sclang classes, help, provider client, and initial C++
  sound-design UGen(s) as one straightforward SuperCollider extension. Keep
  any required headless helper internal to that install/launch workflow.
- Test malformed, oversized, and unauthorized local requests if the selected
  architecture uses local IPC.
- Keep slow or unpredictable work outside the real-time audio thread.

### 4. Package, document, and release

- Provide installation, provider/API-key setup and removal, privacy, API-cost,
  troubleshooting, and uninstall instructions.
- Make the extension and its required plugin/helper artifacts simple to
  install, update, and remove together; document platform-specific prerequisites.
- Review licensing for SuperCollider, any reused example/plugin code,
  dependencies, and distributed binaries before release. SuperCollider itself
  is GPL-3.0; this plan does not assume that generated audio is GPL-licensed.

## Test plan: TDD

Use the project's [Ralph implementation prompt](./RALPH_IMPLEMENTATION_PROMPT.md)
for current shared-skill routing and test-first development mechanics. This
plan retains project-specific coverage criteria below; it does not duplicate
the shared Red-Green-Refactor procedure. Use the
[visual application test plan](./VISUAL_TEST_PLAN.md) for GUI acceptance.

### Coverage strategy

- Test DSP functions, parameter bounds, and deterministic seeded behavior in
  isolation; test the built plugin and sclang class together with short
  SuperCollider NRT renders.
- Test provider request/response adapters, model discovery, stale pricing,
  credit/USD calculations, and errors with fixtures or fakes—never live API
  calls or real credentials in tests.
- Test credential-store behavior through injected fakes and assert key
  redaction/no persistence in logs and project files.
- Test variation-session caps, cancellation, candidate isolation, and
  confirmation before applying changes; use fixed seeds and short renders.
- Require GitHub Actions to pass on every push and pull request. Its canonical
  `bash scripts/run_headless_tests.sh` entrypoint runs source syntax checks,
  Clang static analysis, warning-as-error C++ unit/plugin builds, and all
  Python tests including the SuperCollider NRT integration. The current
  plugin build and CI coverage are macOS-specific; this gate does not replace
  Windows or MacBook Neo validation.
- Use cross-platform CI for Windows 10 x64 and Apple Silicon macOS builds.
  Record any tests that require physical audio hardware as manual checks, and
  never treat subjective listening as a substitute for automated
  determinism/safety tests.
- For GUI changes, launch the real app from SCIDE, exercise the actual visible
  workflow, capture its native window, and inspect the screenshot. Before
  completion, run the full visual scenario on Windows 10 x64 and an actual
  MacBook Neo. Prefer platform accessibility automation; add a minimal
  test-only CLI/in-process driver only if existing tools cannot reliably
  exercise the GUI. A headless test or mock window is not visual sign-off.

Use existing project test/build tools when suitable. If the new project lacks
a test harness for a required behavior, write the test/specification first and
introduce only the smallest maintainable harness needed to run it.

## Validation and acceptance criteria

- **Windows 10 x64:** install, launch, save/remove provider keys, choose a
  provider/model, open the agent window from SCIDE, generate a composition,
  render/play the output file, apply/undo an edit, and handle API/render
  failures without a separate user-facing app.
- **MacBook Neo:** verify the actual macOS version and Apple Silicon build,
  then repeat the same workflow. Do not infer device-specific compatibility
  solely from generic macOS support.
- **Visual application sign-off:** before `RALPH_COMPLETE`, launch the real
  packaged extension from SCIDE on Windows 10 x64 and an actual MacBook Neo.
  Exercise the deterministic mock-provider composition/edit/render workflow,
  capture fresh native screenshots, inspect the images, and record the
  platform versions, results, and artifact references. If either platform or
  screenshot inspection is unavailable, leave this criterion open and report
  the blocker; do not infer success from logs or headless tests.
- **SuperCollider integration:** install the extension through the documented
  Quark/extension workflow; open its GUI from SCIDE without patching/forking
  SuperCollider core.
- **Offline audio:** a prompt can produce a valid composition using the custom
  UGen(s) and a playable audio file without a real-time server or audio device;
  the output duration and format match the selected render settings.
- **In-app sampling loop:** a user-started session creates no more than its
  configured candidate limit (default four), can be stopped early, preserves
  the original project, and keeps each candidate's code, seed, settings, and
  render available for comparison.
- **Custom sound design:** each initial UGen builds and loads on both target
  platforms, exposes documented controls to sclang, and is usable by generated
  compositions.
- **Real-time audition:** the same custom UGen(s) run without audio dropouts
  under representative live workloads on both target platforms.
- **Local provider bridge (if needed):** runs asynchronously, stays on
  loopback or another appropriately restricted local IPC transport, validates
  requests, and keeps API keys out of logs and audio processing; it does not
  require a separate user-facing desktop application.
- **Audio safety:** the UGen produces stable output under real-time load and
  does no network or blocking I/O.
- **Data safety:** provider API keys are absent from project files, logs,
  diagnostics, and crash output; project changes are reviewable and reversible.
- **Provider/model selection:** OpenAI and Anthropic keys can be managed
  independently; available models can be refreshed per configured provider;
  the chosen provider/model is explicit for each request; switching providers
  and reporting unavailable models work without silent fallback.
- **Usage/cost visibility:** each successful model response reports provider
  usage units/tokens and an estimated USD/credit amount when a valid rate is
  available; per-session totals aggregate correctly. Missing or stale rates
  are explicit, never shown as zero.
- **TDD evidence:** keep project verification results in
  `RALPH_PROGRESS.md`; follow the shared test-first workflow routed from the
  project's [Ralph implementation prompt](./RALPH_IMPLEMENTATION_PROMPT.md)
  for behavior changes.
- **Agent quality:** representative music and editing tasks produce valid
  SuperCollider code, explain edits, surface uncertainty, and never claim
  success after a failed operation.

## Risks and constraints

- Generated sclang code can perform actions beyond sound generation. A diff
  and confirmation are important safeguards, but should not be described as a
  true sandbox.
- Required server plugins are platform- and architecture-specific and may be
  tied to the SuperCollider plugin ABI/version; packaging and supported SC
  versions are therefore part of the product.
- OpenAI and Anthropic API availability, model behavior, latency, and cost are
  external dependencies; the app must expose errors and avoid silent retries.
- SuperCollider's upstream README lists Windows 10 as supported and documents
  Apple Silicon builds. MacBook Neo-specific hardware/OS support still needs
  a real-device smoke test.
- NRT rendering is appropriate when all timed events can be prepared in
  advance. Compositions that depend on live user input or server replies need
  real-time mode instead.
- SuperCollider provides extension folders, Quarks, sclang GUI classes, and
  loadable server plugins. Secure HTTPS/model APIs and OS credential-store
  access must be verified; avoid a core fork if a Quark GUI plus a minimal
  headless helper provides the required integrated workflow.
- Review the GPL-3.0 and third-party dependency terms before distributing
  SuperCollider binaries, modified SuperCollider, or derived plugin code.

## Source review

The read-only upstream source-review checkout is in
[`supercollider/`](../supercollider/) at commit `ea52528` (`develop` at
checkout time). The initial runtime/API compatibility target is the official
SuperCollider 3.14.1 release (`Version-3.14.1`, commit
`426edf6d8742e1cc3bd85b51ca0c4e595d37a903`); plugin API headers are pinned to
that release so the built plugin matches its server interface. Key references:

- [SuperCollider platform support and overview](../supercollider/README.md)
- [Writing Unit Generators](../supercollider/HelpSource/Guides/WritingUGens.schelp)
- [Non-Realtime Synthesis (NRT)](../supercollider/HelpSource/Guides/Non-Realtime-Synthesis.schelp)
- [OSC Communication](../supercollider/HelpSource/Guides/OSC_communication.schelp)
- [Using Quarks](../supercollider/HelpSource/Guides/UsingQuarks.schelp)
- [macOS build and Apple Silicon guidance](../supercollider/README_MACOS.md)
- [Windows build and extension guidance](../supercollider/README_WINDOWS.md)
- [SuperCollider GPL-3.0 license](../supercollider/COPYING)
- [Official example plugins](https://github.com/supercollider/example-plugins)
