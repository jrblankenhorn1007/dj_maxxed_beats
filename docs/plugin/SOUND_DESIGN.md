# Sound-Design Palette

This document lives at `docs/plugin/SOUND_DESIGN.md`.

This document tracks the extension's initial custom C++ server-plugin UGens:
their DSP choices, exposed controls, and build/test status. It is updated as
each UGen moves from a pure-DSP core to a full SC plugin with an sclang class
and help file.

## ChaosOsc

**Status:** the DSP core, including the iteration-rate (`freq`) control, is
implemented and unit tested (`plugin/ChaosOsc/Source/ChaosOscCore.hpp`,
`plugin/ChaosOsc/Tests/test_chaos_osc_core.cpp`). The C++ server plugin
wrapper (`plugin/ChaosOsc/Source/ChaosOsc.cpp`) builds against the
SuperCollider 3.14.1 plugin API headers and exports the plugin load symbol.
The sclang class (`ChaosOsc.ar` and `ChaosOsc.kr`) and help file are present
under `plugin/ChaosOsc/Classes/` and `plugin/ChaosOsc/HelpSource/`. The class
and plugin load and render deterministic NRT audio through SuperCollider
3.14.1 on macOS arm64; real-time audition and target-platform coverage remain
open. See [`RALPH_PROGRESS.md`](../RALPH_PROGRESS.md) for earlier evidence
and [`decision_log.md`](../decision_log.md) for the selection rationale.

**DSP:** a logistic-map chaotic oscillator. The map
`x[n+1] = r * x[n] * (1 - x[n])` is chaotic (non-periodic, sensitive to
initial conditions) for growth-rate `r` roughly in `[3.57, 4.0]`, while its
trajectory stays bounded to `[0, 1]` for seeds in that same range. The core
scales the map's state from `[0, 1]` to `[-1, 1]` (`2 * x - 1`), producing a
broadband, deterministic-per-seed signal that is audibly distinct from
standard oscillator/noise UGens. By default the map advances once per output
sample. A lower iteration rate advances it with a double-precision phase
accumulator and linearly interpolates between successive map states, so the
same chaotic trajectory doubles as a smooth modulation source.

**Controls** (`ChaosOsc.ar/kr(chaosAmount = 3.9, seed = 0.5, freq = inf,
mul = 1.0, add = 0.0)`):

- `chaosAmount` — the logistic-map growth rate `r`. Clamped internally to
  `[3.57, 3.999]` (NaN uses `3.57`); audio-rate values are read per sample,
  while scalar and control-rate values are read once per block and control
  updates take effect on the next block. It only affects the output on
  samples where the map advances. Values near the low end sound more
  tonal/periodic, values near the high end sound noisier and more broadband;
  periodic windows inside the range (for example a period-3 cycle around
  3.83–3.84) sound pitched.
- `seed` — initial map state in `(0, 1)`, exclusive of the exact fixed points
  `0.0`/`1.0`. Read at UGen construction; changing it after the Synth starts
  does not reseed the oscillator. Selects a specific chaotic trajectory so a
  composition can be reproduced deterministically.
- `freq` — map iterations per second (Hz), read once per block for any input
  rate. At or above the unit's sample rate (the control rate for `.kr`),
  including the default `inf`, the map advances once per output sample,
  exactly as the original two-argument UGen did. Between `0` and the sample
  rate it advances `freq` times per second and the output is linearly
  interpolated, moving by at most `2 * freq / sampleRate` per output sample.
  `0` or below holds the current value; raising it again resumes from the
  held value. NaN behaves like the default.
- `mul`, `add` — standard output scaling, applied by sclang's `madd` (no
  extra UGen at the defaults).

**DC offset:** the output is not zero-mean. Its mean is roughly `+0.19` at
`chaosAmount = 3.9` and up to about `+0.34` near `3.7`; its maximum is
`chaosAmount / 2 - 1`, and at `3.57` it only spans about `[-0.32, 0.79]`. The
DSP intentionally keeps this mapping so existing compositions render
unchanged; the help file recommends `LeakDC.ar(ChaosOsc.ar(...))` for
audio-rate use.

**Real-time safety:** the core performs only arithmetic on a few `double`
values per sample (map state, interpolation segment, and phase) plus one
iteration-rate conversion per block; it allocates no memory, performs no
I/O, and makes no blocking or locking calls, so it is safe to call from the
audio thread inside the `SCUnit` calc function.

**Verified DSP contract (unit tests in
`plugin/ChaosOsc/Tests/test_chaos_osc_core.cpp`):**

- Output stays within `[-1, 1]` and finite over 100,000 samples at
  `chaosAmount = 3.9`, and across schedules of rate changes with
  out-of-range or NaN controls.
- Identical seed, `chaosAmount`, and rate schedule produce an identical
  sample sequence (determinism required for reproducible candidate
  exploration and for tests).
- Out-of-range `chaosAmount` values (for example `10.0` or `-5.0`) are clamped
  internally and still produce bounded, finite output.
- A NaN `chaosAmount` falls back to the minimum documented value; a NaN `seed`
  falls back to the default midpoint state (`0.5`). This prevents invalid
  floating-point inputs from poisoning the oscillator's state or output.
- Seeding at the map's exact fixed point (`0.0`) still escapes into varying
  output instead of producing silence forever.
- The default rate (never set, `inf`, `freq` at or above the sample or
  control rate, or NaN) reproduces a reference model of the original
  one-step-per-sample DSP bit-exactly, per sample and per block.
- Below the sample rate the output reaches every map state exactly, linearly
  interpolates between them, follows the same trajectory as the full rate,
  advances at the requested rate, and never moves more than
  `2 * freq / sampleRate` per sample.
- `freq <= 0` (including `-inf`) holds the current output exactly, and
  resuming continues smoothly; switching to a low rate starts from the last
  output; `chaosAmount` only matters on samples where the map advances.

**Verified (SuperCollider 3.14.1, macOS arm64, NRT):** the plugin builds
against the API headers for release commit
`426edf6d8742e1cc3bd85b51ca0c4e595d37a903`, exports `_load`, loads in the
matching `scsynth`, and renders deterministic NRT WAVs using the `ChaosOsc`
sclang class. `tests/test_chaososc_nrt.py` verifies duration, finite and
non-silent output, construction-time seed behavior, and control-rate
`chaosAmount` updates. `tests/test_chaososc_rate_nrt.py` verifies in scsynth
that `sclang` accepts and encodes the `inf` default; that two-argument calls,
an explicit `freq = inf`, `freq` equal to the sample rate, and a graph built
with the original two-input layout all render identically and match the
original one-step-per-sample output bit-exactly; that `freq = 100` at 48 kHz
is a smooth linear interpolation of the map; that `freq = 0` holds from the
start and freezes a running Synth after `n_set`; that `ChaosOsc.kr` runs at
the control rate (default and interpolated); and that `mul`/`add` are applied.
Rendering the existing ChaosOsc NRT score and the composition example with
the original plugin and with this version produced byte-identical audio data.

**Not yet verified:** real-time audition without dropouts, Windows 10 x64 or
MacBook Neo plugin ABI/runtime compatibility, or compatibility with
SuperCollider releases other than 3.14.1.
