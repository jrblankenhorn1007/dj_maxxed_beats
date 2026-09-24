# SuperCollider AI Music Agent — Implementation Plan

## Goal

Build a cross-platform AI music assistant for SuperCollider. A user can describe
music they want, have the agent create a procedural composition, render it to an
audio file, and ask for revisions or other project tasks.

The initial target platforms are Windows 10 (64-bit) and the Apple Silicon
MacBook Neo. The assistant supports user-provided OpenAI and Anthropic (Claude)
API keys, and lets the user choose a provider and an available model.

## Recommended architecture

Treat this as a small, coordinated system rather than putting the AI agent
inside a server plugin:

1. **Agent companion app** — owns the chat UI, provider/model selection,
   provider-specific API requests and credentials, project context, change
   previews, and approval flow. It asks the selected model to write or edit
   SuperCollider composition code.
2. **SuperCollider composition/rendering** — `sclang` runs the composition
   logic and can create a `Score`; `scsynth` renders that score to an audio file
   in non-real-time (NRT) mode. The user can optionally audition material
   through a real-time server.
3. **SuperCollider language package (optional)** — a Quark can provide reusable
   composition helpers or an OSC bridge if the companion app needs to inspect
   or control a running session.
4. **C++ server plugin (core audio component)** — supplies the distinctive,
   custom sound-design UGens. Their controls are exposed to sclang so generated
   compositions can use them. It is not the agent, chat UI, or OpenAI client.

Custom C++ sound design is a core requirement. The first sound-design phase
will define a distinctive palette and choose the initial UGen(s); examples to
explore include chaotic or feedback-driven synthesis, unusual modulation, and
custom distortion or spectral processing. The agent should compose with a
stable, tested set of UGen controls rather than generate new C++ source for
each track. SuperCollider's *Writing Unit Generators* guide explains that
UGens run in the audio server's real-time context, where blocking calls are
unsafe. Therefore, model calls and project editing stay in the companion app;
the UGen performs audio DSP only. The same composition can be auditioned live
or rendered offline.

## Proposed user workflow

1. The user describes a track or opens an existing SuperCollider project.
2. The user configures an OpenAI or Anthropic API key, selects that provider,
   and chooses an available model. The app explains that prompts and selected
   project context are sent to the selected provider.
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

1. **Development Ralph loop (outside the app):** repeatedly implements and
   verifies the product against this plan and
   [`RALPH_IMPLEMENTATION_PROMPT.md`](./RALPH_IMPLEMENTATION_PROMPT.md). It
   changes application code; it does not generate music as its task. Each
   completed iteration ends in its own validated commit pushed to the
   configured project GitHub repository.
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

## Component responsibilities

### Companion app

- Manage conversations and the selected project.
- Send prompts and only the project context explicitly selected or needed for
  the task to the provider selected by the user.
- Provide provider adapters for OpenAI and Anthropic (Claude), with a common
  app-facing interface for supported chat, streaming, and structured-edit
  capabilities. Keep provider-specific API behavior behind these adapters.
- Fetch and refresh each configured provider's available model list using its
  model-list API; show provider and model IDs clearly, and persist the selected
  model separately for each provider. Filter or label models according to
  capabilities the app requires. Do not silently substitute a model if the
  selected model is unavailable.
- Produce reviewable composition/code changes, preserve backups/undo, and
  avoid modifying files outside the selected project.
- Start and monitor a render, report progress and actionable failures, and
  clearly identify the resulting audio file.
- Clearly report API, connection, parsing, and execution errors; do not present
  an unsuccessful action as completed.
- Keep provider/API details behind an interface so a provider or model can be
  changed without changing the SuperCollider integration.

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

### SuperCollider Quark / language bridge

- Prefer generating ordinary `.scd` files for the first version; a Quark is
  optional unless shared composition helpers or in-session control are needed.
- If a bridge is needed, provide a minimal, documented protocol for connection
  status and approved project actions. Use OSC for local app-to-sclang
  communication where it fits.
- Bind to loopback only by default, validate message shape and size, and avoid
  accepting commands from arbitrary network peers.
- Keep the bridge optional: code generation and offline rendering should work
  without an already-running interactive SuperCollider session.
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
  whether the agent edits files through a companion window or inside SC IDE.
- Define the first render target (for example, stereo WAV, sample rate, and
  bit depth) and whether live preview is part of the MVP.
- Decide how generated arrangements are represented: direct `.scd` code,
  structured arrangement data translated to `.scd`, or both. Default: generated
  and reviewable `.scd` code.
- Define the first custom sound-design palette and the specific DSP behavior
  for each initial C++ UGen.
- Decide whether the MVP only renders offline or also controls a running
  `sclang` session. Default: file-based compositions and offline render.

### 1. Validate the SuperCollider integration

- Build a minimal C++ UGen with its sclang class and help, then use it in a
  procedural composition, convert that composition to a `Score`, and
  successfully render a WAV using NRT mode.
- Verify the workflow does not need a running real-time server or audio device.
- Verify the custom UGen also works in a real-time audition.
- Prototype a minimal Quark/OSC handshake only if the selected workflow
  requires in-session control.
- Confirm where optional extensions are installed and how users restart/reload
  the language and server.
- Document exact supported SC versions and plugin binary compatibility.

### 2. Implement the safe agent workflow

- Add prompt submission, display of the proposed musical plan, response
  streaming/status, and token management.
- Generate a composition and reviewable file edits; validate paths remain
  under the selected project and show a diff before writing.
- Add backups/undo and clear handling for malformed responses, API errors,
  render failures, and rejected changes.
- Add explicit confirmation before evaluating generated code and generating
  audio.

### 3. Complete core sound-design plugin and optional live bridge

- Implement and package the initial C++ sound-design UGen(s), sclang classes,
  parameter documentation, and test SynthDefs together.
- Implement local OSC and a Quark only if needed for optional live audition,
  status, or approved in-session actions; test malformed, oversized, and
  unauthorized messages.
- Keep slow or unpredictable work outside the real-time audio thread.

### 4. Package, document, and release

- Provide installation, provider/API-key setup and removal, privacy, API-cost,
  troubleshooting, and uninstall instructions.
- Package the companion app, Quark (if used), and required plugin as distinct
  components so users can update or remove them independently.
- Review licensing for SuperCollider, any reused example/plugin code,
  dependencies, and distributed binaries before release. SuperCollider itself
  is GPL-3.0; this plan does not assume that generated audio is GPL-licensed.

## Validation and acceptance criteria

- **Windows 10 x64:** install, launch, save/remove provider keys, choose a
  provider/model, connect to the chosen SC version, generate a composition,
  render/play the output file, apply/undo an edit, and handle API/render
  failures.
- **MacBook Neo:** verify the actual macOS version and Apple Silicon build,
  then repeat the same workflow. Do not infer device-specific compatibility
  solely from generic macOS support.
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
- **Optional SuperCollider integration:** Quark installs cleanly; OSC uses
  loopback by default; valid requests work; invalid/untrusted requests are
  rejected.
- **Audio safety:** the UGen produces stable output under real-time load and
  does no network or blocking I/O.
- **Data safety:** provider API keys are absent from project files, logs,
  diagnostics, and crash output; project changes are reviewable and reversible.
- **Provider/model selection:** OpenAI and Anthropic keys can be managed
  independently; available models can be refreshed per configured provider;
  the chosen provider/model is explicit for each request; switching providers
  and reporting unavailable models work without silent fallback.
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
- Review the GPL-3.0 and third-party dependency terms before distributing
  SuperCollider binaries, modified SuperCollider, or derived plugin code.

## Source review

The local upstream checkout is in [`supercollider/`](./supercollider/) at
commit `ea52528` (`develop` at checkout time). Key references:

- [SuperCollider platform support and overview](./supercollider/README.md)
- [Writing Unit Generators](./supercollider/HelpSource/Guides/WritingUGens.schelp)
- [Non-Realtime Synthesis (NRT)](./supercollider/HelpSource/Guides/Non-Realtime-Synthesis.schelp)
- [OSC Communication](./supercollider/HelpSource/Guides/OSC_communication.schelp)
- [Using Quarks](./supercollider/HelpSource/Guides/UsingQuarks.schelp)
- [macOS build and Apple Silicon guidance](./supercollider/README_MACOS.md)
- [Windows build and extension guidance](./supercollider/README_WINDOWS.md)
- [SuperCollider GPL-3.0 license](./supercollider/COPYING)
- [Official example plugins](https://github.com/supercollider/example-plugins)
