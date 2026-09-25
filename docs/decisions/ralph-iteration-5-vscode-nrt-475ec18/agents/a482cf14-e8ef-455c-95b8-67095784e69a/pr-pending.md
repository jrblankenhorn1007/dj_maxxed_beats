# Iteration 5 Agent / PR Record

- **Agent:** Copilot VS Code agent host
- **Runtime/session ID:** `a482cf14-e8ef-455c-95b8-67095784e69a`
- **Branch:** `refs/heads/ralph/iteration-5-vscode-nrt-475ec18`
- **Base SHA:** `475ec183f262594a6f4ab3d08cf1ee9bec833553`
- **Implementation commit SHA:** pending
- **Pull request:** pending publication and creation

## Decisions

- Target the official SuperCollider 3.14.1 release API at commit
  `426edf6d8742e1cc3bd85b51ca0c4e595d37a903` after a runtime NRT attempt
  showed that the development-header API version 7 is rejected by the 3.14.1
  server, which expects API version 3. Scope the header cache by revision so
  stale headers cannot be reused.
- Preserve both input modes for the audio-rate ChaosOsc UGen: read audio-rate
  `chaosAmount` per sample and broadcast scalar/control-rate values per block.
  Keep `seed` as a construction-time value and validate both behaviors with a
  short fixed-seed NRT score.
- Use three temporary output channels in the ignored test build directory to
  compare a baseline, a Synth whose seed control changes after construction,
  and a Synth whose control-rate `chaosAmount` changes. Render twice and
  compare float samples for determinism; do not retain or commit generated
  audio.
- Keep the official runtime image, OSC scores, WAVs, and build products under
  ignored `.runtime/` and `.build/` paths. The upstream SuperCollider source
  checkout was not created or modified.

## Recovered failures

- The initial NRT Red run rejected the plugin with API version `7` versus
  expected `3`. Switching the header pin to release commit `426edf6` and
  scoping its cache aligned the plugin and runtime.
- A subsequent server abort came from duplicate discovery of the same
  built-in plugin directory in the `-U` path. De-duplicating resolved plugin
  paths and disabling default synthdef loading (`-D 0`) resolved the harness
  issue.
- Once the plugin loaded, repeated NRT renders differed by up to
  `0.1996920258`, and the control-rate amount signal differed before its
  update. `ChaosOsc::next()` had read beyond a control-rate input buffer.
  Branching on `isAudioRateIn(0)` fixed the over-read; final repeated renders
  were identical and the scheduled control update changed output as intended.

## Unresolved coverage

- The PR is intentionally left for coordinator review and the configured
  merge-commit process; no remote-main merge is claimed.
- Windows 10 x64, an actual MacBook Neo, real-time audition, and SuperCollider
  releases other than 3.14.1 remain unverified.
