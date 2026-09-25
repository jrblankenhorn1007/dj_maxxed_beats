# Procedural Chaos Garden composition

`examples/procedural_chaos_garden.scd` is a reviewable, seed-driven
SuperCollider composition using the existing `ChaosOsc` UGen. The extension
class `MaxxedBeatsComposition.score(duration, seed)` creates a timed NRT
`Score`; the render helper executes it with `scsynth -N`. This workflow does
not boot a real-time server, open an audio device, or modify SuperCollider
core.

## Build and render

Build the pinned ChaosOsc plugin once from the repository root:

```sh
bash plugin/ChaosOsc/Tests/build_plugin_smoke_test.sh
```

Then render a nine-second, 48 kHz stereo float WAV:

```sh
python3 scripts/render_composition.py --output chaos-garden.wav
```

The renderer retains the generated OSC score beside the WAV as
`chaos-garden.wav.osc`. The default composition seed is `0.37`; the duration
must be between 4 and 300 seconds. A chosen seed can be repeated to reproduce
the render:

```sh
python3 scripts/render_composition.py \
  --output chaos-garden-seed-037.wav \
  --duration 9 \
  --seed 0.37
```

Existing WAVs and OSC sidecars are preserved: by default the renderer stops
if either output already exists. Pass `--overwrite` only when you intend to
replace both files.

The sample rate defaults to 48 kHz and can be selected with
`--sample-rate`; output is always two-channel IEEE float32 WAV. `sclang` and
`scsynth` must be on `PATH`, or their executable paths can be supplied via
`SCLANG` and `SCSYNTH` or the matching command-line options. The helper also
uses the SuperCollider built-in `Plugins` directory next to `scsynth`; set
`SC_DEFAULT_PLUGIN_PATH` to a platform-separated list if the runtime stores
those plugins elsewhere. `--plugin-dir` selects a prebuilt `ChaosOsc.scx`
directory when it is not at the development default.

The build step needs the compiler and the pinned SuperCollider 3.14.1 plugin
API headers (fetched and cached by the existing build script). After the
plugin and runtime are available, the render step itself performs no network
calls and uses only non-realtime synthesis. The automated NRT test verifies
the resulting WAV independently for format, duration, finite/non-silent
channels, and deterministic fixed-seed output.
