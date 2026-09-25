# Sound-Design Palette

This document lives at `docs/plugin/SOUND_DESIGN.md`.

This document tracks the extension's initial custom C++ server-plugin UGens:
their DSP choices, exposed controls, and build/test status. It is updated as
each UGen moves from a pure-DSP core to a full SC plugin with an sclang class
and help file.

## ChaosOsc (in progress)

**Status:** DSP core implemented and unit tested
(`plugin/ChaosOsc/Source/ChaosOscCore.hpp`,
`plugin/ChaosOsc/Tests/test_chaos_osc_core.cpp`). The C++ server plugin
wrapper (`plugin/ChaosOsc/Source/ChaosOsc.cpp`) builds against the
SuperCollider 3.14.1 plugin API headers and exports the plugin load symbol.
The audio-rate sclang class and help file are present under
`plugin/ChaosOsc/Classes/` and `plugin/ChaosOsc/HelpSource/`. The class and
plugin load and render deterministic NRT audio through SuperCollider 3.14.1
on macOS arm64; real-time audition and target-platform coverage remain open.
See [`RALPH_PROGRESS.md`](../RALPH_PROGRESS.md) for exact evidence and
[`decision_log.md`](../decision_log.md) for the selection rationale.

**DSP:** a logistic-map chaotic oscillator. The map
`x[n+1] = r * x[n] * (1 - x[n])` is chaotic (non-periodic, sensitive to
initial conditions) for growth-rate `r` roughly in `[3.57, 4.0]`, while its
trajectory stays bounded to `[0, 1]` for seeds in that same range. The core
scales the map's state from `[0, 1]` to audio-rate `[-1, 1]` on every sample,
producing a broadband, deterministic-per-seed signal that is audibly distinct
from standard oscillator/noise UGens.

**Controls:**

- `chaosAmount` — the logistic-map growth rate `r`. Clamped internally to
  `[3.57, 3.999]`; audio-rate values are read per sample, while scalar and
  control-rate values are broadcast across each audio block and control
  updates take effect on the next block. Values near the low end sound more
  tonal/periodic, values near the high end sound noisier and more broadband.
- `seed` — initial map state in `(0, 1)`, exclusive of the exact fixed points
  `0.0`/`1.0`. Read at UGen construction; changing it after the Synth starts
  does not reseed the oscillator. Selects a specific chaotic trajectory so a
  composition can be reproduced deterministically.
- Planned but not yet implemented: a `rate`-style control that decouples the
  map's update rate from the audio sample rate (for example, updating the map
  once per N samples and interpolating), so the same chaotic trajectory can be
  used as a slow modulation source as well as an audio-rate oscillator.

**Real-time safety:** the core performs only arithmetic on a single `double`
per call; it allocates no memory, performs no I/O, and makes no blocking
calls, so it is safe to call once per sample from the audio thread once
wrapped in a `UGen::next` callback.

**Verified DSP contract (unit tests, see [`RALPH_PROGRESS.md`](../RALPH_PROGRESS.md)):**

- Output stays within `[-1, 1]` and finite over 100,000 samples at
  `chaosAmount = 3.9`.
- Identical seed and `chaosAmount` produce an identical sample sequence
  (determinism required for reproducible candidate exploration and for tests).
- Out-of-range `chaosAmount` values (for example `10.0` or `-5.0`) are clamped
  internally and still produce bounded, finite output.
- A NaN `chaosAmount` falls back to the minimum documented value; a NaN `seed`
  falls back to the default midpoint state (`0.5`). This prevents invalid
  floating-point inputs from poisoning the oscillator's state or output.
- Seeding at the map's exact fixed point (`0.0`) still escapes into varying
  output instead of producing silence forever.

**Verified:** the plugin builds against the API headers for SuperCollider
3.14.1 (release commit
`426edf6d8742e1cc3bd85b51ca0c4e595d37a903`), exports `_load`, loads in the
matching `scsynth`, and produces a deterministic NRT WAV using the
`ChaosOsc` sclang class. The NRT check verifies duration, finite/non-silent
output, construction-time seed behavior, and control-rate `chaosAmount`
updates. This is macOS arm64 runtime coverage only.

**Not yet verified:** real-time audition without dropouts, Windows 10 x64 or
MacBook Neo plugin ABI/runtime compatibility, or compatibility with
SuperCollider releases other than 3.14.1.
