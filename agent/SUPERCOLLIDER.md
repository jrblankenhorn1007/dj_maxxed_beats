# SuperCollider guidance

## Verified project target

Use the project's documented initial runtime/API target, SuperCollider
3.14.1, unless the selected installation and its documentation establish a
different supported version. Do not imply that this version has been verified
on every target device: current plugin/NRT evidence is macOS arm64 only;
Windows 10 x64, an actual MacBook Neo, real-time audition, and other releases
remain unverified.

Prefer file-based `.scd` compositions and offline NRT rendering for the MVP.
Use ordinary SuperCollider language constructs and confirm unfamiliar
classes, methods, argument names, and plugin requirements in documentation for
the actual installed version. Do not invent or assume APIs from memory. Label
untested code and compatibility as unverified rather than presenting them as
working.

## ChaosOsc

The project's verified custom-UGen constructors are
`ChaosOsc.ar(chaosAmount, seed, freq, mul, add)` and
`ChaosOsc.kr(chaosAmount, seed, freq, mul, add)`; their defaults are `3.9`,
`0.5`, `inf`, `1.0`, and `0.0`. Two-argument calls such as
`ChaosOsc.ar(3.82, seed)` render bit-identically to the original
two-argument plugin. Before `mul`/`add` the output stays in `[-1, 1]`, but it
is not zero-mean: the mean is roughly `+0.19` at `chaosAmount` 3.9 and up to
about `+0.34` near 3.7, and at 3.57 the output only spans about
`[-0.32, 0.79]`. Wrap audio-rate use in `LeakDC.ar(ChaosOsc.ar(...))` before
mixing, and scale it appropriately when composing with other signals.

The plugin clamps `chaosAmount` to `[3.57, 3.999]`. Audio-rate `chaosAmount`
is read per sample; scalar and control-rate values are read once per block,
and control-rate changes take effect on the next block. `freq` is the
map-iteration rate in Hz and is read once per block: at or above the unit's
sample rate (the control rate for `.kr`), including the default `inf`, the map
advances once per output sample; lower positive values advance at that rate
and linearly interpolate between successive map states, which makes a smooth
modulation source; `0` or below holds the current value; NaN behaves like the
default. The seed is captured when the Synth is created; changing it later
does not reseed that Synth. Use the UGen only when the matching plugin and
language class are available.

Keep provider calls, file access, project editing, and other blocking work out
of UGen/audio callbacks. Treat composition code as executable code, not as
data that is automatically safe to evaluate.

## Renderable composition files

An approved render runs the entry `.scd` file in a separate headless `sclang`
process and then renders the result with `scsynth` in NRT mode. Write entry
files so that:

- the last expression returns a `Score` (or an Array of `[time, OSC message]`
  pairs) that sends `[0.0, [\d_recv, def.asBytes]]` for every SynthDef it
  uses; do not boot a server or call `.play`, `.add`, `s.sync`, or `Server`;
- settings come from `~mbRender` (`duration`, `sampleRate`, `numChannels`,
  `seed`), with defaults such as `~mbRender ? (duration: 30, seed: 0.37)` so
  the file still evaluates elsewhere;
- events stay within `~mbRender[\duration]`: later events are dropped and the
  render ends exactly at that duration;
- `~mbRender[\seed]` drives deterministic choices (the language random seed is
  also set from it);
- peaks stay below full scale (about -1 dBFS) and the result is not silent.
  The workflow checks build and render success, duration, format, non-finite
  samples, silence, and clipping, but not musical quality;
- only built-in classes, `ChaosOsc`, and the MaxxedBeats classes are used, and
  the file does not read or write files, start processes, or use the network.
