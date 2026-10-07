# dj_maxxed_beats

`dj_maxxed_beats` is a planned AI-assisted music and sound-design extension for
SuperCollider. The long-term goal is a Quark that runs inside SuperCollider:
people describe a musical idea, review generated `.scd` composition changes,
render audio with SuperCollider, and optionally explore variations. The plan
envisions OpenAI and Anthropic model choices, but that provider workflow is not
implemented. The planned design keeps synthesis in SuperCollider rather than
adding a separate user-facing desktop app.

> **Current state: the ChaosOsc plugin works; the AI music app does not exist
> yet.** The ChaosOsc server plugin can be built, installed into
> SuperCollider, and played in real time or rendered offline. There is no
> Quark GUI, provider integration or API-key workflow, or release packaging
> for the larger AI assistant. The current checks do not use API keys or call
> a model provider.

## What exists today

- **ChaosOsc server plugin:** a C++17 logistic-map chaotic oscillator UGen
  with `ChaosOsc.ar`/`ChaosOsc.kr(chaosAmount, seed, freq, mul, add)`. The
  `freq` control sets the map's iteration rate; below the sample rate the
  output is linearly interpolated, so it works as an audio-rate noise source
  and as a smooth chaotic modulator. See the
  [ChaosOsc build and install guide](./plugin/ChaosOsc/README.md) and the
  [sound-design notes](./docs/plugin/SOUND_DESIGN.md).
- **Build and install:** a CMake build (universal arm64/x86_64 on macOS,
  `.so` on Linux, MSVC `.scx` on Windows) and `scripts/install_chaososc.py`,
  which installs the plugin, class, and help into SuperCollider's user
  Extensions folder.
- **Composition prototype:** `MaxxedBeatsComposition` and
  `examples/procedural_chaos_garden.scd`, rendered offline by
  `scripts/render_composition.py`.
- **Developer verification:** DSP unit tests, source and help (SCDoc)
  checks, plugin builds, NRT integration tests, an installed-layout
  end-to-end test, and an opt-in real-time server test.

There is still no assistant window to open.

## Install the ChaosOsc plugin

Requires CMake 3.16+, a C++17 compiler, Python 3, and SuperCollider 3.14.1
(the plugin API version it is built against). From the repository root:

```sh
python3 scripts/install_chaososc.py
```

Then, in SuperCollider, recompile the class library
(**Language > Recompile Class Library**), reboot the server, and try:

```supercollider
{ LeakDC.ar(ChaosOsc.ar(3.9, 0.37)) * 0.1 ! 2 }.play;
```

Use `python3 scripts/install_chaososc.py --uninstall` to remove it. The
[plugin guide](./plugin/ChaosOsc/README.md) covers manual CMake builds,
Windows and Linux paths, and troubleshooting.

## Run the developer checks

Run these commands from the repository root. They test the current prototype;
they are not commands for installing or running an AI music application.

### Full headless test suite

```sh
bash scripts/run_headless_tests.sh
```

This is the recommended complete check. It runs the quality gate followed by
all Python tests, including the SuperCollider plugin/NRT integration. It
requires Bash, Python 3, Clang, a C++17 compiler, and matching `sclang` and
`scsynth` executables. Put both SuperCollider command-line tools on `PATH`, or
provide their paths:

```sh
SCLANG=/absolute/path/to/sclang \
SCSYNTH=/absolute/path/to/scsynth \
bash scripts/run_headless_tests.sh
```

The plugin build also needs network access to fetch its pinned API headers
when they are not already cached. The suite does not launch SCIDE, a GUI, a
real-time server, or audio hardware.

### Static analysis and warning-free builds

```sh
bash scripts/run_quality_checks.sh
```

This quality gate is also run by the full headless suite. It checks the
first-party Bash and Python source syntax, treats Python warnings as errors,
runs Clang's static analyzer on the ChaosOsc sources, and builds/tests both
the DSP core and SuperCollider plugin with C++ warnings treated as errors.
The pinned SuperCollider API headers are treated as system headers so only
project-source warnings block the build. The plugin analysis/build requires
network access to fetch the pinned headers when they are not cached. Set
`CLANGXX` to select the Clang analyzer or `CXX` to select the C++ compiler.

### Pure DSP test

```sh
bash plugin/ChaosOsc/Tests/run_tests.sh
```

Requires Bash and a C++17 compiler. The script defaults to `clang++`; set
`CXX` to use another C++17 compiler. This test does not need SuperCollider.

### SuperCollider language source-contract test

```sh
PYTHONDONTWRITEBYTECODE=1 python3 tests/test_chaososc_language_contract.py
```

Requires Python 3. It checks the `ChaosOsc.ar` source signature, defaults, and
help text; it does not load the class in SuperCollider.

### Plugin smoke build

```sh
bash plugin/ChaosOsc/Tests/build_plugin_smoke_test.sh
```

Requires Bash, Python 3, and a C++17 compiler (`CXX` can select the compiler).
The script builds the plugin against the public SuperCollider 3.14.1 plugin
API headers, performs Clang static analysis, treats project compiler warnings
as errors, and requires `nm` to verify the exported `_load` symbol. If those
pinned headers are not already in the local cache, the build needs network
access to fetch them from `raw.githubusercontent.com`. A successful smoke
build does not itself run the plugin in `scsynth`.

### Optional NRT runtime integration

```sh
SCLANG=/absolute/path/to/sclang \
SCSYNTH=/absolute/path/to/scsynth \
PYTHONDONTWRITEBYTECODE=1 \
python3 tests/test_chaososc_nrt.py
```

Requires Python 3, Bash, a C++17 compiler, and matching `sclang` and `scsynth`
executables. The test also builds the plugin, so it needs network access if
the pinned plugin API headers are not cached. It uses the supplied executable
paths; if the variables are omitted, the script looks for `sclang` and
`scsynth` on `PATH`. The recorded runtime check uses SuperCollider 3.14.1. It
generates a short test score, renders two WAV files, and checks plugin/class
loading, finite and non-silent output, repeat-render determinism,
construction-time seed behavior, and a control-rate update. This remains a
developer integration test, not an end-user render workflow.

### Opt-in real-time server test

```sh
DJMB_REALTIME_AUDIO_TESTS=1 \
SCLANG=/absolute/path/to/sclang \
SCSYNTH=/absolute/path/to/scsynth \
PYTHONDONTWRITEBYTECODE=1 \
python3 tests/test_chaososc_realtime.py
```

Boots a real-time `scsynth` on the default CoreAudio output device, runs
ChaosOsc and a 64-synth live workload on private buses (hardware outputs stay
silent), and checks the captured audio, server health, and CPU. It is skipped
unless `DJMB_REALTIME_AUDIO_TESTS=1`, because CI runners have no audio device.

## Targets and tested coverage

The project targets **Windows 10 x64** and **Apple Silicon macOS**, with
explicit validation planned on an actual **MacBook Neo**. These are project
targets, not claims of current platform support.

The latest local verification ran on an actual **MacBook Neo** (`Mac17,5`,
Apple A18 Pro, macOS 26.5.2) with SuperCollider 3.14.1: the full headless
suite (98 tests), the installed-layout end-to-end test, and the real-time server test
(CoreAudio, 48 kHz, peak CPU about 4.5% with 67 concurrent synths) all
passed. GitHub Actions runs the headless gate on macOS 14 and a
**Plugin Builds** workflow on macOS 14, Ubuntu, and Windows Server runners
for every push and pull request. That workflow builds the plugin (universal
on macOS, MSVC on Windows), checks its exported `load` symbol, exercises the
installer, and renders an NRT smoke test with the Windows build of
SuperCollider 3.14.1.

Still unverified: a physical Windows 10 x64 machine, real-time audio on
Windows, a Linux `scsynth` run, the GUI/SCIDE workflow, SuperCollider
versions other than 3.14.1, and release packaging of the AI assistant.

## Project documentation

- [Implementation plan](./docs/IMPLEMENTATION_PLAN.md) — product scope,
  planned architecture, implementation slices, and acceptance criteria.
- [Visual test plan](./docs/VISUAL_TEST_PLAN.md) — the live SCIDE workflow and
  platform-specific visual acceptance gates.
- [Current implementation status](./docs/implementation_status.md) — what is
  implemented and the current verification/platform coverage.
- [Progress evidence](./docs/RALPH_PROGRESS.md) — iteration-by-iteration
  build, test, and runtime evidence.
- [Per-branch implementation archive](./docs/implementation/README.md) —
  branch-specific prompts, agent handoffs, decision links, and code-review
  records.
- [Decision log](./docs/decision_log.md) — dated project and architecture
  decisions.
- [Ralph implementation prompt](./docs/RALPH_IMPLEMENTATION_PROMPT.md) — the
  project entry point for the shared development workflow and project sources
  of truth.
- [Sound-design notes](./docs/plugin/SOUND_DESIGN.md) — ChaosOsc's DSP
  behavior, controls, and remaining verification gaps.
- [Documentation index](./docs/README.md) — a guide to the documents under
  `docs/`.

## License

See the repository-root [LICENSE](./LICENSE).
