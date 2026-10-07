# MaxxedBeats AI assistant — cross-worker contract (iteration 7)

Requirements come from [IMPLEMENTATION_PLAN.md](../IMPLEMENTATION_PLAN.md),
[VISUAL_TEST_PLAN.md](../VISUAL_TEST_PLAN.md), and `agent/*.md`. This file
only fixes the interfaces between parallel workers. Extend an interface you
own and document it in your design doc; never change another worker's
interface—report the need to the coordinator instead.

## Layout and conventions

- Quark root `extension/`: `MaxxedBeats.quark`, `Classes/`, `HelpSource/`.
  Class prefix `MB`; the SCIDE entry point is `MaxxedBeats.gui`.
- Class folders: `Classes/Core` (coordinator: `MBError`), `Classes/Providers`
  (worker-01), `Classes/Workflow` (worker-02), `Classes/GUI` (worker-03).
  `Classes/MaxxedBeatsComposition.sc` already exists (worker-02).
- Non-secret settings: `Platform.userConfigDir +/+ "MaxxedBeats"` (JSON).
  Secrets never reach settings, project files, logs, the post window, process
  arguments, long-lived environment variables, temp files, or error text.
- Project data: `<project>/.maxxedbeats/` (backups, sessions). Renders go to
  `<project>/renders/` with unique, never-overwritten names and a JSON
  metadata sidecar (prompt summary, provider/model, seed, settings, duration,
  checks; no secrets).
- Asynchronous everywhere: provider, network, and render work never blocks
  the language and never runs on the audio thread. Callbacks run on `AppClock`.
- Callback style: `onSuccess: { |result| }`, `onFailure: { |error| }` with an
  `MBError`. Long operations return a handle that responds to `.cancel`.

## MBError (coordinator; already in the parent branch)

`MBError(kind, detail)`; `kind` is one of `\auth \network \rateLimit \server
\parse \unavailableModel \cancelled \validation \render \config \io`;
`detail` must already be redacted.

## Provider layer (worker-01)

- `MBProvider` base; `MBOpenAIProvider`, `MBAnthropicProvider`, and
  `MBMockProvider` (deterministic and offline; drives tests and the visual
  plan). `MBProviderRegistry.default` exposes `.providers` and `.at(id)` for
  ids `\openai`, `\anthropic`, `\mock`.
- Provider: `.id`, `.displayName`, `.listModels(onSuccess, onFailure)` →
  Array of `(id:, displayName:, provider:, usable: Boolean, note: String)`;
  `.complete(request, onSuccess, onFailure)` → cancellable handle.
  - request `(model: String, system: String, messages: [(role: \user or
    \assistant, content: String)], maxOutputTokens: Integer, temperature:
    Float or nil)`.
  - response `(provider: Symbol, model: String, text: String, usage:
    (inputTokens:, outputTokens:, cachedInputTokens:) or nil, requestId:)`.
- `MBCredentialStore` (`.default`; `.fake` for tests): `.hasKey(id,
  onResult)`, `.storeKey(id, key, onSuccess, onFailure)`, `.removeKey(id,
  onSuccess, onFailure)`, `.validateKey(id, onSuccess, onFailure)`. Backends:
  macOS Keychain, Windows Credential Manager, Linux Secret Service.
- `MBModelCatalog`: `.refresh(id, onSuccess, onFailure)`, `.models(id)`,
  `.lastRefreshed(id)`, `.isStale(id)`, `.selectedModel(id)`,
  `.selectModel(id, modelId)` (persisted per provider). Never substitutes a
  model silently; an unavailable selection is an `\unavailableModel` error.
- `MBUsageMeter`: `.record(response)` → `(provider:, model:, inputTokens:,
  outputTokens:, cachedInputTokens:, usd: Float or nil, credits: Float or
  nil, rateStatus: \ok or \missing or \stale, rateTable: String)`;
  `.sessionTotals`, `.history`, `.clearHistory`. 100 credits per estimated
  USD; unknown cost is nil, never 0.

## Workflow layer (worker-02)

- `MBProject.open(dir)`: `.root`, `.files`, `.read(relPath)`,
  `.resolve(relPath)` (rejects paths outside the project), `.backups`,
  `.undo(onSuccess, onFailure)`, `.apply(proposal, confirmed: Boolean,
  onSuccess, onFailure)` (refuses unless confirmed; backs up first).
- `MBAgent(project, provider, catalog, meter)`: `.propose(userPrompt,
  context, onSuccess, onFailure)` → proposal `(plan: String, summary: String,
  edits: [MBEdit], usage: <meter record>, raw: String)`. Instructions come
  from `agent/*.md`.
- `MBEdit`: `.path`, `.oldText`, `.newText`, `.isNew`, `.diffString`.
- `MBRenderer.render(project, entryPath, settings (duration:, sampleRate:,
  numChannels:), approved: Boolean, onProgress, onSuccess, onFailure)` →
  separate headless `sclang` builds the Score, `scsynth` renders NRT; result
  `(path:, metadataPath:, duration:, sampleRate:, numChannels:, checks:
  (finite:, silent:, clipped:, durationOk:))`. Generated code is never
  evaluated in the user's interpreter.
- `MBVariationSession(agent, project, maxCandidates: 4)`: `.start(prompt,
  onCandidate, onDone, onFailure)`, `.stop`, `.candidates`, `.apply(index,
  confirmed: Boolean, onSuccess, onFailure)`. Candidates live under
  `<project>/.maxxedbeats/sessions/`; the original project is unchanged until
  a confirmed apply.

## GUI, packaging, CI (worker-03)

- `MaxxedBeats.gui` opens the agent window. The provider/model selector is
  labeled **Choose your DJ** and always shows the explicit provider and model
  ids. Everything is wired through the interfaces above; nothing evaluates
  generated code or renders without explicit approval.
- One installer installs and removes the Quark and the ChaosOsc plugin
  together.

## Tests

- `tests/test_mb_*.py` run sclang scripts headlessly with isolated
  `HOME`/XDG/`LOCALAPPDATA` and `--include-path extension/Classes` (plus
  `plugin/ChaosOsc/Classes` when needed); follow `tests/test_chaososc_nrt.py`.
- No live provider calls or real keys in tests: use `MBMockProvider`, fakes,
  or a loopback fake server.
