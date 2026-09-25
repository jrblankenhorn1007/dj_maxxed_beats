# Decision record — worker-01 / PR pending

- **Run/task:** `ralph-product-end-condition-20260925-015713-e03cb755` /
  `composition-nrt-workflow`
- **Worker:** `worker-01 / NRT composition`
- **Runtime agent ID:** `copilotcli:/2b879fb9-33a5-494a-8506-0b6a794ab270`
- **Branch:** `refs/heads/ralph/composition-nrt-worker-01-20260925-015713-e03cb755`
- **Base `origin/main` SHA:** `f9e1bb3edafff1cc6d24c640a8e0ed38f5bf49fe`
- **Implementation commit SHA:** pending
- **PR:** pending; the normal integration path is a worker-owned pull request,
  opened only after the implementation commit and coordinator review.

## Decisions

### Use a procedural Score-backed `.scd` plus an explicit NRT renderer

- **Context:** The existing ChaosOsc class/plugin and deterministic test-only
  NRT score provide a validated synthesis primitive, but there is no
  user-facing composition or render command.
- **Alternatives:** Extend the existing plugin test fixture into a user
  workflow, require a booted real-time server, or add a standalone desktop
  renderer.
- **Rationale:** A reviewable `.scd` composition and a small CLI that writes an
  NRT `Score` then invokes `scsynth -N` are the smallest product-facing slice
  that reuses the existing UGen without requiring an audio device or
  SuperCollider core changes.
- **Consequences:** The acceptance check will independently inspect the WAV
  header, sample count, finite/non-silent channels, and repeated fixed-seed
  output. The SuperCollider runtime/plugin remain prerequisites for rendering;
  untested OS/device coverage will be recorded explicitly.

### Require explicit confirmation before replacing render outputs

- **Context:** The new render command accepted an output path but originally
  overwrote existing WAV and OSC-score files without warning, which could
  destroy user work.
- **Alternatives:** Replace files silently, create backups automatically, or
  refuse existing targets unless the user passes an explicit flag.
- **Rationale:** A command-line `--overwrite` flag is a clear user action and
  the smallest safe choice for this file-based prototype; it avoids hidden
  backup policy and prevents accidental data loss.
- **Consequences:** The default preserves an existing WAV or score sidecar.
  Tests verify both files remain byte-identical after a refused render; a
  caller must pass `--overwrite` to replace them.

## Recovered test issue

- The first post-implementation run of
  `SCLANG=.../sclang SCSYNTH=.../scsynth PYTHONDONTWRITEBYTECODE=1 python3
  tests/test_composition_nrt.py` passed the real NRT render but failed a
  source check because the `.scd` comment mentioned `.play`. The check was
  refined to inspect executable code after stripping the explanatory block
  comment; the next run passed both tests. No product behavior was weakened.

## Recovered build setup timeout

- A subsequent test run timed out after 180 seconds while repeating
  `plugin/ChaosOsc/Tests/build_plugin_smoke_test.sh`. The already-built arm64
  plugin and pinned-header cache were present, and no build process remained
  after timeout. Test setup now rebuilds only when the plugin is absent or a
  tracked build input is newer than the artifact. The full composition test
  then passed in 3.169 seconds, including three fresh deterministic NRT
  renders. No credentials were exposed and no plugin source/test files were
  changed.
