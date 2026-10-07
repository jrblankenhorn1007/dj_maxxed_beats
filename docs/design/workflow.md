# Workflow layer design (worker-02)

Implements the contract's workflow layer (`extension/Classes/Workflow`):
proposing edits, reviewing and applying them, undo, approved offline
renders, and the user-started variation ("sampling") loop. Plan references:
*Proposed user workflow* steps 3–6, *Two separate Ralph loops* item 2, and
the *Quark / language bridge* separation of proposing from evaluating code.

| Class | Responsibility |
| --- | --- |
| `MBProject` | Path confinement, file listing/reading, edit preparation, confirmed apply with backups, undo |
| `MBEdit`, `MBDiff` | One reviewable edit; unified diff (3 lines of context) |
| `MBAgent` | System prompt from `agent/*.md`, request with only the selected context, provider call, response validation |
| `MBResponseFormat` | The strict `maxxedbeats.proposal/1` response contract |
| `MBRenderer`, `MBRenderProcess`, `MBAudioCheck` | Approved headless render: separate `sclang` → Score → `scsynth -N`; checks; sidecar |
| `MBVariationSession` | Bounded, user-started candidate loop with isolated workspaces |
| `MBWorkflowJSON` | Strict RFC 8259 parser and deterministic writer |
| `MBWorkflowHandle`, `MBWorkflowTry` | Cancellable handles; exception capture that is safe on sclang 3.14.1 |

Providers, the model catalog, and the usage meter are used only through the
contract interfaces (`provider.id`, `.complete`, `catalog.selectedModel(id)`,
`meter.record(response)`); tests use Event-based fakes.

## Interfaces (contract plus documented extensions)

All asynchronous callbacks run on `AppClock`; failures are `MBError`s.

- `MBProject.open(dir)` → throws `MBError(\io)` if missing; refuses a
  filesystem root. `.root` (real path), `.files` (visible regular files,
  sorted, excluding hidden entries, symlinks, and `renders/`; max 400 files,
  depth 8), `.read(rel)` (≤ 256 KiB), `.resolve(rel)`, `.backups`,
  `.undo(onSuccess, onFailure)`, `.apply(proposal, confirmed, onSuccess,
  onFailure)`. Extensions: `.exists(rel)`, `.resolveEditable(rel)`,
  `.prepareEdit((path:, action:, oldText:, newText:))` → `MBEdit`,
  `.dataDir`, `.rendersDir`, `.backupsDir`, `.sessionsDir`.
- `MBEdit`: `.path .oldText .newText .isNew .diffString`, plus `.kind`
  (`\create \replace \edit`), `.before`/`.after` (complete file contents at
  proposal time), `.asMetadata`.
- `MBAgent(project, provider, catalog, meter)`: `.propose(prompt, context,
  onSuccess, onFailure)` → `MBWorkflowHandle` (`.cancel` → `\cancelled`).
  Proposal: `(plan:, summary:, edits:, usage:, raw:)` plus `assumptions:`,
  `questions:`, `uncertainty:`, `entry:`, `render:`, `seed:`, `provider:`,
  `model:`, `requestId:`, `prompt:`. Extensions: `.buildRequest(prompt,
  context)` (for previews/disclosure), `MBAgent.systemPrompt`,
  `MBAgent.instructionsDir` (override), `.maxOutputTokens` (16000),
  `.temperature` (nil).
  - `context`: `(files: [rel], notes: String, history: [(role: \user or
    \assistant, content:)], entry: rel, seed: Float, variation: (index:,
    count:))`. Limits: 24 files, 384 KiB of context and history, 32 KiB
    prompt.
- `MBRenderer.render(project, entry, settings, approved, onProgress,
  onSuccess, onFailure)` → handle. Result: `(path:, metadataPath:,
  duration:, sampleRate:, numChannels:, checks:)` plus `sampleFormat:`,
  `seed:`, `entry:`, `warnings:`, `workDir:`.
- `MBVariationSession(agent, project, maxCandidates: 4, renderSettings,
  context)`: `.start(prompt, onCandidate, onDone, onFailure, approveRenders:
  false)`, `.stop`, `.candidates`, `.apply(index, confirmed, onSuccess,
  onFailure)`. Extensions: `.renderCandidate(index, approved, onProgress,
  onSuccess, onFailure, overrides)`, `.seeds`, `.state` (`\idle \running
  \stopped \done \failed`), `.id`, `.dir`; `onDone.value(candidates,
  stopped)`.

## Prompt assembly

`MBAgent.systemPrompt` concatenates `ROLE.md`, `WORKFLOW.md`,
`SUPERCOLLIDER.md`, and `SAFETY.md` in that order, each preceded by an
`<!-- agent/NAME -->` marker. They are found in `MBAgent.instructionsDir`, else
`<quark>/agent`, else `<quark>/../agent` (the repository layout). A missing or
empty file is `MBError(\config)`; no request is sent.

The single user message contains the request, then each **selected** file
(read through `MBProject` confinement) in a fence longer than any backtick
run inside it, the chosen entry, notes, the required seed and variation
index when present, and a reminder of the response format. Unselected files
and the project file list are never sent. The model is the catalog's
explicit selection for the provider; none selected is `MBError(\config)`.
Prior turns may be passed as `history` (`\user`/`\assistant` only).

## Structured response: `maxxedbeats.proposal/1`

The model must reply with exactly one JSON object (an optional single
` ```json ` fence is tolerated). `agent/WORKFLOW.md` gives the model the same
specification and an example; worker-01's `MBMockProvider` should emit it.

| Field | Type | Rules |
| --- | --- | --- |
| `format` | string | required, exactly `"maxxedbeats.proposal/1"` |
| `plan` | string | required, non-empty, ≤ 16 KiB |
| `summary` | string | required, non-empty, ≤ 4 KiB |
| `assumptions`, `questions`, `uncertainty` | string[] | optional, ≤ 32 items of ≤ 2 KiB |
| `edits` | object[] | required (may be `[]`), ≤ 16 |
| `edits[].path` | string | project-relative, `/`-separated; `.scd .md .txt .json`; no absolute, `..`, `.`, empty, hidden, `renders/`, `.maxxedbeats/`, backslash, drive, control characters, or symlinked components; each path once |
| `edits[].action` | string | `create` (must not exist), `replace` (must exist, full contents), `edit` (`oldText` must occur exactly once) |
| `edits[].oldText` | string | only and required for `edit` |
| `edits[].newText` | string | ≤ 256 KiB each, ≤ 1 MiB total, no NUL; must change the file |
| `entry` | string | optional `.scd` that is edited or exists |
| `render` | object | optional `{duration: 1–600 s, sampleRate: 22050/32000/44100/48000/88200/96000/192000, numChannels: 1–8}` |
| `seed` | number | optional, 0 < seed < 1 |

Unknown fields anywhere, duplicate JSON keys, and non-standard JSON are
rejected. Error mapping: empty text, prose, malformed or non-standard JSON →
`MBError(\parse)`; valid JSON with the wrong shape, an oversized response
(> 512 KiB), an out-of-project or reserved path, a stale `oldText`, or
credential-like content (`sk-…` keys, PEM private keys) →
`MBError(\validation)`. Error details never echo the response or a secret.
Usage is recorded with the meter even when the response is rejected, because
the tokens were spent. Validation never writes files.

## Apply, backups, undo

`apply` refuses unless `confirmed === true` (not merely truthy). It then
re-validates every edit (paths, and that each file still equals the
proposal's `before`, or still does not exist for `create`), writes the
backup `<project>/.maxxedbeats/backups/<YYYYMMDD-HHMMSS-NNN>/` (`before/`,
`after/`, `manifest.json` with `files: [(path, existed)]`, `summary`,
`undone`), and only then writes the files, reading each back to verify. A
failed write rolls back the files already written. `undo` restores the
newest backup that is not undone: changed files get `before`, created files
are deleted. It refuses (and changes nothing) if any file differs from
`after`, so later user edits are never overwritten. Backups are kept after
undo (`undone: true`).

## Render pipeline

1. **Approval and validation** – `approved === true`; entry passes
   `resolveEditable` and is an existing `.scd`; settings: `duration`,
   `sampleRate` (48000), `numChannels` (2), `sampleFormat` (`float`, `int24`,
   `int16`), `seed` (0.5), `timeout` (120 s per process), `name`, `metadata`
   (only `summary prompt provider model candidate sessionId plan`, redacted,
   ≤ 2000 chars), `silenceThresholdDb` (−60), `clipThreshold` (0.999).
   Tool overrides: `sclang`, `scsynth`, `pluginPaths` (replaces the
   Extensions folders), `builtinPluginPaths`, `includePaths`; class
   defaults `MBRenderer.defaultSclang/defaultScsynth/defaultPluginPaths/
   defaultBuiltinPluginPaths`. macOS defaults are the running app's
   `Contents/MacOS/sclang`, `Contents/Resources/scsynth`, and
   `Contents/Resources/plugins`; Windows uses `sclang.exe`, `scsynth.exe`, and
   `plugins` in `Platform.resourceDir`. Plugin folders default to
   `Platform.userExtensionDir`, `Platform.systemExtensionDir`, and the folder
   of the installed ChaosOsc class when it holds `ChaosOsc.scx`/`.so`
   (`MBRenderer.chaosOscPluginDirs`; on Windows
   `%LOCALAPPDATA%\SuperCollider\Extensions\ChaosOsc`). Missing tools →
   `\config`.
2. **Reservation** – output `<project>/renders/<entry>-<YYYYMMDD-HHMMSS>[-N].wav`;
   the `.json` sidecar is written immediately as a placeholder so concurrent
   renders never share a name. Nothing is ever overwritten. Diagnostics go
   to `<project>/.maxxedbeats/renders/<id>/` (`runner.scd`,
   `entry-snapshot.scd`, `score.osc`, `sclang.log`, `scsynth.log`).
3. **Build** – a separate `sclang` runs a generated `runner.scd` with
   `--include-path` for the Quark's `Classes` and the folder of the installed
   `ChaosOsc` class (de-duplicated, nested paths dropped), via
   `exec env -i HOME=<work>/home XDG_*… TMPDIR PATH LANG … < /dev/null >
   sclang.log 2>&1`: no inherited environment (so no secrets) and an isolated
   HOME. The runner sets `~mbRender = (duration, sampleRate, numChannels,
   seed)` and the random seed, evaluates the entry, accepts a `Score` or an
   Array of `[time, msg…]` events, drops events at or after the duration,
   adds an end marker one sample before the duration, and writes the Score.
   Timeout, cancellation, or a class-library compile failure kills the child.
   **Windows** (verified on the hosted Windows runner): sclang finds the
   user's folders with `SHGetKnownFolderPath`, not environment variables, so
   isolation is explicit. The child runs `sclang.exe -l <work>/sclang_conf.yaml
   runner.scd`; the YAML sets `excludeDefaultPaths: true` and lists
   `<sclang dir>/SCClassLibrary`, the Quark's `Classes`, the ChaosOsc class
   folder, and `<work>/isolation`, which holds a generated class extension
   that points `Platform.userAppSupportDir`/`userConfigDir`/`userExtensionDir`
   into the isolated home and disables startup files (no user startup file,
   Quarks, or other Extensions are loaded). Both children are started by
   `Data/windows/MaxxedBeatsLaunch.ps1` from a JSON spec written next to the
   log (`<log>-launch.json`: program, args, environment, log): a cleared
   environment with only `HOME USERPROFILE APPDATA LOCALAPPDATA TEMP TMP
   SystemRoot windir PATH` (System32) and the XDG/LANG entries, stdin closed,
   stdout then stderr in the log, no window. No shell parses any path, so
   spaces, backslashes, and `& % ^` are safe. Kill = `taskkill /F /T /PID`
   (the launcher's tree); the exit callback fires once the whole tree has
   exited, then the isolated `home/` and `tmp/` are deleted.
4. **Render** – `scsynth -U <builtin:plugins…> -o <channels> -m 65536 -D 0
   -N score.osc _ out.wav <rate> WAV <format>` with the same isolation. A
   `UGen '<name>' not installed` line becomes an actionable `\render` error.
5. **Checks** – `MBAudioCheck` reads the file in chunks on `AppClock`:
   `rendered`, `finite` (no NaN/inf), `silent` (peak < −60 dBFS), `clipped`
   (any |sample| ≥ 0.999), `durationOk` (|actual − requested| ≤ max(2
   blocks, 2 ms); NRT rounds up to a 64-sample block), `formatOk` (rate and
   channels), `ok` (all good), plus `peak/peakDb/rms/rmsDb/
   nonFiniteSamples/clippedSamples`. Musical quality is not judged.
6. **Sidecar** (`maxxedbeats.render/1`): `status`, `createdAt`, `entry`,
   `output`, `settings`, `seed`, `duration`, `sampleRate`, `numChannels`,
   `checks`, `warnings`, `droppedEvents`, `renderSeconds`, `workFolder`, and
   the whitelisted metadata. No secrets or tool paths.

Progress events: `(stage: \building | \rendering | \checking | \done,
fraction:, message:)`. On any failure or cancellation the reserved `.wav`
and `.json` are removed and logs are kept; errors name the stage, the first
error line, and the log path. The isolated child `home/` and `tmp/` are
deleted after each render.

## Variation loop

`start` is the only way to run; a session runs once. Candidates are
proposed sequentially (never in parallel) with fixed seeds
`frac((i + 1) × 0.618…)` rounded to 4 decimals (0.618, 0.2361, 0.8541,
0.4721, …), passed both to the model (“Required seed”, “candidate i of n”)
and to the renderer. Each candidate copies the project (≤ 64 MiB) into
`.maxxedbeats/sessions/<id>/candidate-NN/project/`, applies its edits there,
and records `code` (path → contents), `diff`, `entry` (context entry, else
proposal entry, else the first edited `.scd`), `settings` (defaults ←
proposal `render` ← session `renderSettings`; seed fixed), `render`,
`checks`, `status` (`\proposed \rendering \rendered \failed`), and `error`
in `candidate.json`; the session writes `session.json`. A `\parse` or
`\validation` failure becomes a failed candidate that counts toward the cap;
any other provider error ends the session with `onFailure`. `.stop` cancels
the in-flight request or render and calls `onDone(candidates, true)`;
`onCandidate` runs before the next request, so stopping inside it prevents
further requests. `maxCandidates` is clamped to 1–16.

Rendering inside a session requires `start(..., approveRenders: true)`,
which the GUI must pass only after the user confirmed rendering up to N
generated candidates in a separate process, or `.renderCandidate(index,
true, …)`. `apply(index, confirmed)` applies the selected candidate's
proposal to the original project through `MBProject.apply` (stale checks,
backup, undo).

## Decisions

1. **Strict JSON proposal format** with unknown-field rejection and a format
   id, rather than free text with code blocks: the workflow can validate
   paths and sizes before showing a diff, and malformed output can never
   reach files.
2. **Three edit actions** (`create`, `replace`, `edit` with a unique
   `oldText`) and a `before` snapshot per edit: small edits stay reviewable,
   and stale proposals are refused instead of merged.
3. **Undo refuses after later user changes** rather than overwriting them.
4. **Render isolation by `env -i` and an isolated HOME** for both child
   processes (Windows: a cleared environment via the PowerShell launcher plus
   `sclang -l` with `excludeDefaultPaths` and redirected user folders);
   generated code never runs in the user's interpreter and never sees
   inherited environment secrets. This is isolation, not a sandbox.
5. **End marker one sample before the duration** so block-aligned renders
   have exactly the requested length.
6. **Session rendering needs its own approval flag** (`approveRenders`,
   default false), keeping "approve before rendering" true for the loop.
7. **`MBWorkflowTry`**: on SuperCollider 3.14.1, a `try` that catches an error
   raised while message arguments are being evaluated corrupts the caller's
   pending sends (a later unrelated call is skipped or misrouted). Guarded
   code runs on its own `Routine` stack instead; all workflow classes use it.

## Known gaps and requests

- Windows process launching is verified on the hosted Windows runner (render,
  variation, and GUI-integration suites, plus the installed-package smoke
  test); a physical PC is the user's manual check. Linux launching and default
  tool paths are implemented but not exercised in CI.
- Packaging (worker-03) must ship `agent/*.md` with the Quark (`<quark>/agent`)
  for installed use; the repository layout is found automatically.
- Other workers' sclang code should avoid plain `try` for the reason above.
- No real-time preview/audition; the GUI plays the rendered file.
