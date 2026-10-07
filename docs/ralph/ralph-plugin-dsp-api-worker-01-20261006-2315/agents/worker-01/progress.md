# worker-01 progress: ChaosOsc iteration-rate DSP and sclang API

Branch `ralph/plugin-dsp-api-worker-01-20261006-2315`, base `fa6decd`.
Host: macOS 26.5.2 arm64, Apple clang 17.0.0, Python 3.9.6, SuperCollider
3.14.1 (`SCLANG`/`SCSYNTH` from the mounted runtime). Scratch logs and the
saved legacy plugin live in the git-ignored `tests/.build/`.

## Baseline

- `SCLANG=… SCSYNTH=… bash scripts/run_headless_tests.sh` at `fa6decd`:
  exit 0, `Ran 33 tests … OK`.
- Saved the base plugin binary, class, NRT renders, and composition renders
  under `tests/.build/legacy/` for an old-vs-new comparison.

## Red (tests written first, failing for the right reason)

1. `bash plugin/ChaosOsc/Tests/run_tests.sh` → compile errors
   `no member named 'iterationIncrement' in namespace 'chaososc'` and
   `no member named 'kDefaultIterationRate'` (API missing). With API-only stubs
   (no behaviour): `19 test(s) failed`: increment mapping, interpolation,
   hold, and continuity. The legacy-equivalence checks passed.
2. `python3 -m unittest tests/test_chaososc_language_contract.py` →
   `FAILED (failures=21)`: missing `*ar`/`*kr` freq/mul/add signatures and
   missing help documentation (freq, `.kr`, DC/LeakDC).
3. `python3 -m unittest tests/test_chaososc_rate_nrt.py` → setUpClass error.
   sclang reported `ERROR: Message 'kr' not understood. RECEIVER: ChaosOsc`.
   The first run hung until the 120 s timeout, so the score now catches errors
   and exits 1 within 0.4 s.
4. The same NRT test with the new class but the saved legacy plugin binary
   failed 3 tests: low-freq output was not interpolated (max error 1.75),
   `freq = 0` did not hold, and the `.kr` 75 Hz step was 0.0275, above the
   0.0031 limit. The default-equivalence test passed, so the Python reference
   model matches the original plugin.
5. `python3 -m unittest tests/test_agent_instructions.py` →
   `FAILED (failures=11)`: new signature, freq, and LeakDC wording were
   missing, and `planned update-rate control` was still present.

## Green

- `ChaosOscCore.hpp`: `kDefaultIterationRate` (+inf), `iterationIncrement`,
  `setIterationRate`, a phase-accumulator `next` with linear interpolation and
  hold, and a constant-amount `processBlock` overload. `run_tests.sh`:
  `All tests passed` (47 PASS). The tests also pass with `-O0`,
  `-O2 -ffp-contract=fast`, `-O2 -ffp-contract=off`, and
  `-O3 -march=native`. `clang++ --analyze` is clean.
- `ChaosOsc.cpp`: reads freq once per block with `in0(2)` and compares it
  with `sampleRate()`. Two-input graphs fall back to the default rate.
  `build_plugin_smoke_test.sh`: analyzer clean, `-Werror` build, and
  `Verified exported plugin load symbol: _load`.
- `ChaosOsc.sc`: `*ar`/`*kr` with `freq = inf, mul = 1.0, add = 0.0` and
  `.madd`. sclang prints `ChaosOsc audio [3.9, 0.5, inf]`. Unity `madd`
  returns the ChaosOsc itself. The score's SynthDef bytes contain float32
  `7f800000` (+inf).
- Help: the SCDoc parse test passes. A manual sclang check found that all 4
  example code blocks compile and build SynthDefs. They were not played.
- `tests/test_chaososc_rate_nrt.py`: `Ran 7 tests … OK`.
- `tests/test_agent_instructions.py` and the language contract: OK.

## Backward compatibility evidence

- I rendered `tests/chaososc_nrt_score.scd` and the composition (seeds 0.37 and
  0.73) with the base plugin and class, then with this branch. The WAV `data`
  and `fmt ` chunks are byte-identical. Only the timestamped `PEAK` chunk
  differs.
- In the NRT test, the 2-argument output matches a Python model of the
  original algorithm bit-exactly. An explicit `inf`, `freq = 48000`, and a
  graph built with the two-input layout (`ChaosOsc.multiNew('audio', …)`)
  produce the same output.

## Mutation check

- I changed the wrapper to pass `fullSampleRate()` instead of `sampleRate()`.
  `test_control_rate_constructor_runs_at_control_rate` failed with a max
  error of 1.60, then I reverted the change.

## Final gate

- `SCLANG=… SCSYNTH=… bash scripts/run_headless_tests.sh` → exit 0,
  `Ran 43 tests … OK`, with 0 skipped. The 33 baseline tests passed, plus 3
  new language-contract tests and 7 new rate-NRT tests. The quality checks
  passed: bash/Python syntax, `clang --analyze`, the `-Werror` unit build
  (47 PASS), and the `-Werror` plugin build with `_load`.

## Unverified gaps

- Not verified: real-time audition, dropouts, and CPU cost on a live server.
  Also not verified: Windows 10 x64, an actual MacBook Neo, and SuperCollider
  releases other than 3.14.1.
- The help examples were compiled and built, not played.
- Historical docs outside this worker's paths still describe the
  two-argument/audio-rate-only API: `docs/implementation_status.md` (line 21),
  `docs/RALPH_PROGRESS.md`, `docs/decision_log.md` (DEC-021 and the "later
  decoupled update-rate" note), and `README.md` (lines 22 and 88 mention only
  `ChaosOsc.ar`). The coordinator owns those files.
