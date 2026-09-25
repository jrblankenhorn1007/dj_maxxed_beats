# dj_maxxed_beats

`dj_maxxed_beats` is a planned AI-assisted music and sound-design extension for
SuperCollider. The long-term goal is a Quark that runs inside SuperCollider:
people describe a musical idea, review generated `.scd` composition changes,
render audio with SuperCollider, and optionally explore variations. The plan
envisions OpenAI and Anthropic model choices, but that provider workflow is not
implemented. The planned design keeps synthesis in SuperCollider rather than
adding a separate user-facing desktop app.

> **Current state: prototype only.** This is not an installable or user-facing
> AI music application. There is no Quark GUI, provider integration or API-key
> workflow, end-user composition workflow, packaging, or release support. What
> exists today is a ChaosOsc DSP/plugin prototype, its SuperCollider language
> class and help source, and developer tests that include a test-only NRT
> score. The current checks do not use API keys or call a model provider.

## What exists today

- **ChaosOsc DSP prototype:** a C++17 logistic-map oscillator core and its
  SuperCollider server-plugin wrapper.
- **SuperCollider source:** the `ChaosOsc.ar` language class and help file.
- **Developer verification:** a pure-DSP test, a source-contract test, a
  plugin smoke build, and an optional SuperCollider non-realtime (NRT)
  integration test. The NRT test uses a fixed test score; it is not an
  end-user composition or rendering workflow.

These components are useful for development and verification only. There is
no extension to install or assistant window to open.

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

## Targets and tested coverage

The project targets **Windows 10 x64** and **Apple Silicon macOS**, with
explicit validation planned on an actual **MacBook Neo**. These are project
targets, not claims of current platform support.

The latest local runtime verification is **macOS 26.5.2 arm64 with
SuperCollider 3.14.1**. GitHub Actions runs the quality and headless test
gates on every push and pull request, and on manual dispatch, using macOS 14
and the official SuperCollider 3.14.1 runtime. These checks are not a
Windows build and neither macOS run was on an actual MacBook Neo.
Windows 10 x64, a real MacBook Neo, real-time audition, the GUI/SCIDE workflow,
SuperCollider versions other than 3.14.1, and release binaries remain
unverified. Packaging and release support have not been implemented.

## Project documentation

- [Implementation plan](./docs/IMPLEMENTATION_PLAN.md) — product scope,
  planned architecture, implementation slices, and acceptance criteria.
- [Visual test plan](./docs/VISUAL_TEST_PLAN.md) — the live SCIDE workflow and
  platform-specific visual acceptance gates.
- [Current implementation status](./docs/implementation_status.md) — what is
  implemented and the current verification/platform coverage.
- [Progress evidence](./docs/RALPH_PROGRESS.md) — iteration-by-iteration
  build, test, and runtime evidence.
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
