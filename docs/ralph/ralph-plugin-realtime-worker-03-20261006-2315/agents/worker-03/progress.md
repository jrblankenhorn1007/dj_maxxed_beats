# Worker-03 progress — real-time ChaosOsc audition

## Iteration 1 — DONE (pending coordinator review)

- **Run/worker:** `ralph-plugin-realtime-worker-03-20261006-2315` / worker-03.
- **Branch/worktree:** `ralph/plugin-realtime-worker-03-20261006-2315` at
  `/Users/jrblankenhorn/dj_maxxed_beats.worktrees/ralph-plugin-realtime-worker-03-20261006-2315`,
  base `fa6decd`. Not merged, pushed, or PR'd.
- **Scope:** new opt-in real-time test `tests/test_chaososc_realtime.py` +
  sclang driver `tests/chaososc_realtime.scd`; this log. No plugin
  source/class/help, CMake/CI, or README changes. Relies only on
  `ChaosOsc.ar(chaosAmount, seed)`.
- **Host:** macOS 26.5.2 (25F84) arm64 MacBook, Python 3.9, SuperCollider
  3.14.1 CLI from the read-only mount
  (`SCLANG=.../SuperCollider.app/Contents/MacOS/sclang`,
  `SCSYNTH=.../SuperCollider.app/Contents/Resources/scsynth`, paths under
  `/Users/jrblankenhorn/dj_maxxed_beats.worktrees/plugin-fix-and-completion/.runtime/mount`).

### What the test does

- Skips (`unittest.SkipTest`) unless `DJMB_REALTIME_AUDIO_TESTS=1`; once
  enabled it never skips (missing `SCLANG`/`SCSYNTH`, build failure, no
  output-only device, or boot failure all FAIL with diagnostics).
- Builds `plugin/ChaosOsc/Tests/.build/ChaosOsc.scx` with the smoke script
  only when missing/stale; isolated `HOME`/`TMPDIR`/`XDG_*` under
  `tests/.build/realtime-*`; free 127.0.0.1 UDP port (57110–57130 avoided);
  `ugenPluginsPath` = ChaosOsc build dir + built-in plugins (inode-deduped);
  `sclang --include-path plugin/ChaosOsc/Classes`; `numInputBusChannels = 0`;
  CoreAudio default output device at its current sample rate.
- Audition: warm-up instantiation (reported separately), 1.5 s settle, then
  one timestamped bundle starts `ChaosOsc.ar(3.9, 0.37)`, a twin with the
  same values via controls, 64 workload voices, and a RecordBuf recorder at
  the root tail. Workload `chaosAmount` is `.set` every 0.25 s (values in
  [3.4, 4.2], partly outside the clamp); the twin is `.set` to 3.7 at 1.0 s;
  voices are then freed. All ChaosOsc output goes to private buses; the
  recorder also captures hardware out 0/1, which must be exact zeros.
- Python checks: exit 0; no `FAILURE IN SERVER`/`not found`/`not installed`/
  `late`/`ERROR`/`exception`/`DJMB_RT FAIL` lines; CoreAudio driver line;
  input device == the output-only device; `/status` per phase
  (`numSynths` 66 → 2 → 0, `serverRunning=true`); live-window peak CPU <
  50 %; ≥5 live `/status` replies; 67 synths concurrently live; `/quit`
  acknowledged and `Server ... exited with exit code 0`; no leftover scsynth
  (port/process-group scan, killed on any failure path); WAV float32,
  5 channels, `frames == round(2 s × SR)`, finite, |x| ≤ 1, non-silent to the
  end, twin bit-identical to the reference until the scheduled `.set`.
- Evidence files (ignored): `tests/.build/chaososc-realtime/{chaososc_realtime_capture.wav,summary.json,sclang_output.log}`.

### TDD evidence

1. **Red (missing driver):** test written first;
   `DJMB_REALTIME_AUDIO_TESTS=1 python3 -m unittest -v tests.test_chaososc_realtime.ChaosOscRealtimeAuditionTests`
   → FAIL `missing real-time audition script .../tests/chaososc_realtime.scd`;
   without the variable → `skipped 'real-time audio test is opt-in: ...'`.
2. **Red (real boot hang — root cause found):** first real run booted
   CoreAudio (`SC_AudioDriver: sample rate = 48000, block size 512`) but
   never answered `/status`; boot-timeout FAIL after 30 s. scsynth had picked
   `"MacBook Neo Microphone" Input Device` despite `-i 0`. SC 3.14.1
   `server/scsynth/SC_CoreAudio.cpp` (+ `.h`): without `-H` it always takes
   the default input device, and `UseSeparateIO()` (input ≠ output device)
   makes `DriverStart` call `AudioDeviceStart(mInputDevice, ...)` regardless
   of `mNumInputs`, so macOS gated the boot on microphone consent.
   **`numInputBusChannels = 0` alone does not avoid the prompt on this
   hardware.** Fix: Python resolves the CoreAudio default output device via
   `system_profiler SPAudioDataType -json` (refusing devices with inputs;
   override `DJMB_REALTIME_AUDIO_DEVICE`) and sclang sets
   `ServerOptions.device` to it, so in == out == `MacBook Neo Speakers`
   (`Streams: 0` input) and no separate input IOProc starts.
3. **Red (CPU/scan):** next run passed everything except `maxPeakCPU=52.09`
   (all per-phase peaks 6.7 %); it also printed `ERROR: Message '+' not
   understood` (sclang `dict[k] = v` returns the dict) that the output scan
   missed. scsynth `peakCPU` = worst callback over ~1 s
   (`mMaxPeakCounter = buffersPerSecond`). A probe (scratch, 64 synths per
   bundle, 1.5 s settles) showed a first-instantiation transient, not
   ChaosOsc cost: ChaosOsc first 15.92 %, repeat 4.05 %/4.21 %, 8 voices
   0.60 %, 1 voice 0.55 %, built-in **SinOsc first use 34.82 %**, 8×8
   bundles 4.27 %. Fixes: warm-up with an identical bundle reported as
   `warmupMaxPeakCPU` and excluded from the asserted live window after the
   settle; dictionary bug fixed; scan now flags `ERROR`/`exception`.
4. **Red→Green (cleanup matcher):** contract test with an `exec -a
   "scsynth -u PORT"` impostor plus a bystander shell mentioning
   `/opt/scsynth -u PORT`; the original loose regex killed both
   (`[20371, 20372] != [20371]`); argv[0]-anchored regex passes.
5. **Green:** all checks pass (results below).

### Real-time results (MacBook Neo Speakers, 48 kHz nominal, 512-frame HW buffer, 64-sample blocks)

Five consecutive opt-in runs
(`DJMB_REALTIME_AUDIO_TESTS=1 python3 -m unittest tests.test_chaososc_realtime.ChaosOscRealtimeAuditionTests`, ~6.8 s each, all exit 0):

| run | live peak CPU % | live max avg % | warm-up peak % | boot peak % | actual SR | capture wall s | twin divergence s |
|---|---|---|---|---|---|---|---|
| 1 | 4.550 | 3.409 | 4.625 | 0.609 | 48000.215 | 2.181 | 1.000 |
| 2 | 4.246 | 3.632 | 4.037 | 0.639 | 48000.219 | 2.179 | 1.000 |
| 3 | 4.423 | 3.612 | 2.099 | 0.648 | 48000.213 | 2.181 | 1.000 |
| 4 | 4.473 | 3.410 | 3.967 | 0.498 | 48000.212 | 2.181 | 1.000 |
| 5 | 4.396 | 3.584 | 1.980 | 0.502 | 48000.214 | 2.179 | 1.000 |

Other runs: warm-up transients of 27.85 % and 28.10 % (live peaks 4.41 %,
4.43 %); opt-in gate run: live peak 4.23 %, live max avg 3.74 %, warm-up
5.76 %, boot 1.09 %, 16 live `/status` replies (28 total), workload phase
66 synths / 392 UGens, final `s.avgCPU` 1.47 % / `s.peakCPU` 4.16 %.
Every passing run: 96000 frames (2.000 s), reference RMS 0.627, workload
RMS 0.215, hardware outputs exact zeros, twin divergence at frame 48000
(exactly the bundle-scheduled 1.000 s), clean `/quit` (exit code 0), no
leftovers. Informational: the RT reference is bit-exact with a
double-precision logistic map from float32(0.37), r = float32(3.9), at
offset 1 (the ctor's priming sample) — not asserted, so DSP changes such as
worker-01's `freq` input cannot break the audition.

### Negative-path checks (manual, ad-hoc scratch scripts; not committed, since deleted)

- **Failed boot:** `SCSYNTH=<fake script exiting 1> SC_DEFAULT_PLUGIN_PATH=<built-in plugins> DJMB_REALTIME_AUDIO_TESTS=1 python3 -m unittest -v tests.test_chaososc_realtime.ChaosOscRealtimeAuditionTests`
  → FAIL in 2.2 s: `fake scsynth: cannot open audio device`,
  `Server ... exited with exit code 1.`, `DJMB_RT FAIL ERROR: scsynth exited while booting`.
- **Plugin missing from `ugenPluginsPath`** (driver run via the module's
  helpers): 1688 flagged lines (`*** ERROR: SynthDef djmbChaosOscRtVoice not found`,
  `/fail /n_free Node ... not found`), `numSynths` 0 in every phase → the
  test fails; no leftover processes.
- Missing `SCLANG`/`SCSYNTH` with the opt-in is an automated contract test.

### Gate and other commands

- Without opt-in: `env -u DJMB_REALTIME_AUDIO_TESTS SCLANG=... SCSYNTH=... bash scripts/run_headless_tests.sh`
  → exit 0, `Ran 38 tests in 9.344s`, `OK (skipped=1)` (33 existing + 4
  new contract tests + skipped audition); re-run at the final commit →
  exit 0, `Ran 38 tests in 29.330s`, `OK (skipped=1)` (55 s wall).
- With opt-in: `DJMB_REALTIME_AUDIO_TESTS=1 SCLANG=... SCSYNTH=... bash scripts/run_headless_tests.sh`
  → exit 0, `Ran 38 tests in 54.929s`, `OK` (102 s wall).
- `PYTHONDONTWRITEBYTECODE=1 PYTHONWARNINGS=error python3 -m unittest -v tests/test_chaososc_realtime.py`
  → 4 OK + 1 skipped; `git diff --cached --check` clean.

### macOS privacy side effect (needs a human decision)

The unpinned first attempt made coreaudiod check scsynth for
`kTCCServiceMicrophone`: TCC logged `AUTHREQ_PROMPTING ... subject=com.microsoft.VSCode`
at 19:32:42.920 and resolved it at 19:33:12.278 with `authValue=2,
authReason=2` (allowed by user consent), creating a Microphone record for
**VS Code**. Revoke in System Settings › Privacy & Security › Microphone
if unwanted. Since the device pin (19:36:20–19:52), `log show` (subsystem
`com.apple.TCC`) shows 28 microphone `preflight=yes` status queries,
0 `preflight=no` requests, 0 prompts, and 0 microphone record changes.

### Unverified gaps / risks

- Verified only on built-in `MacBook Neo Speakers` at 48 kHz/512; other
  rates, USB/Bluetooth devices, and other SC versions are untested. Duplex
  default outputs (inputs on the same device) are refused, by design.
- Nothing was listened to; silence is proven by exact-zero hardware buses.
- scsynth does not report CoreAudio overloads; health is inferred from
  `/status` peak CPU (≤ ~1 s windows, polled every 0.25 s), absence of
  `late`/failure output, and real-time capture pacing.
- The first-instantiation transient (4–55 % observed) is reported, not
  asserted; a slower or loaded machine could push it higher.
- macOS-only (`system_profiler`, `ps`); hosted CI always skips the audition.
