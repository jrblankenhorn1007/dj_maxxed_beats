# ChaosOsc — build, install, and use

ChaosOsc is a SuperCollider server plugin (UGen) plus its language class and
help file: a deterministic, seed-controlled logistic-map chaotic oscillator.
This folder is a standalone CMake project that builds the plugin and installs
a complete SuperCollider extension folder:

```text
<Extensions>/ChaosOsc/
├── ChaosOsc.scx        # ChaosOsc.so on Linux (no "lib" prefix)
├── Classes/            # ChaosOsc.sc (the language-side class)
├── HelpSource/         # ChaosOsc.schelp (SCIDE help)
└── README.md, LICENSE
```

## Requirements

- **SuperCollider 3.14.1.** The plugin is compiled against the SuperCollider
  3.14.1 plugin API (pinned commit `426edf6d8742e1cc3bd85b51ca0c4e595d37a903`).
  Other SuperCollider versions are unverified.
- **CMake 3.16 or newer.**
- **A C++17 compiler:** macOS Xcode Command Line Tools (`xcode-select
  --install`); Linux GCC or Clang (`sudo apt install build-essential cmake`);
  Windows Visual Studio 2022 or newer (or its Build Tools) with the *Desktop
  development with C++* workload (MSVC x64).
- **Python 3** (standard library only) for the installer and for fetching the
  pinned SuperCollider plugin API headers. The first configure of each build
  directory fetches those headers from `raw.githubusercontent.com` into
  `plugin/.sc-plugin-api-cache/`; to build offline, point at a SuperCollider
  source checkout instead (`--sc-path` / `-DSC_PATH=`).

## Install with the installer (recommended)

From the repository root:

```sh
python3 scripts/install_chaososc.py            # macOS / Linux
py -3 scripts\install_chaososc.py              # Windows
```

It configures, builds (Release), and runs `cmake --install` into your
SuperCollider user Extensions directory — the same folder as
`Platform.userExtensionDir`:

| OS      | Default Extensions directory                                  |
|---------|---------------------------------------------------------------|
| macOS   | `~/Library/Application Support/SuperCollider/Extensions`      |
| Linux   | `${XDG_DATA_HOME:-~/.local/share}/SuperCollider/Extensions`   |
| Windows | `%LOCALAPPDATA%\SuperCollider\Extensions`                     |

(SuperCollider also honors `XDG_DATA_HOME` on macOS; so does the installer.)

| Option | Effect |
|---|---|
| `--extensions-dir DIR` | Install into `DIR/ChaosOsc` instead of the default. |
| `--build-dir DIR` | CMake build directory (default `plugin/ChaosOsc/build`). |
| `--sc-path DIR` | Use the plugin API headers of a SuperCollider source checkout (`DIR/include/...`) instead of fetching them. |
| `--dry-run` | Print the plan and exact CMake commands; change nothing. |
| `--force` | Replace an existing `ChaosOsc` folder that the installer did not create. |
| `--uninstall` | Remove a `ChaosOsc` folder that the installer created. |

The installer writes a `.chaososc-install-marker` file into the folder it
installs. It refuses to overwrite an existing `ChaosOsc` folder without that
marker unless you pass `--force`, and `--uninstall` only ever removes a
marked folder. A re-install replaces the previous marked install cleanly. It
warns about other `ChaosOsc` copies it finds in the Extensions directories.
Installer builds do not treat compiler warnings as errors, so a newer
compiler's new warning cannot block an install (CI and the tests do).

### After installing (or uninstalling): restart both halves of SuperCollider

1. **Recompile the class library** so sclang sees the `ChaosOsc` class: in
   SCIDE choose *Language > Recompile Class Library*, or evaluate
   `thisProcess.recompile`.
2. **Reboot the server** so scsynth loads (or unloads) the plugin: `s.reboot`.
3. Smoke test in SCIDE (quiet; `LeakDC` removes the DC offset):

   ```supercollider
   { LeakDC.ar(ChaosOsc.ar(3.9, 0.37)) * 0.1 ! 2 }.play
   ```

See the `ChaosOsc` help file (SCIDE: put the cursor on `ChaosOsc` and press
Cmd-D / Ctrl-D) for every argument and more examples.

## Build and install manually with CMake

macOS / Linux (from the repository root):

```sh
cmake -S plugin/ChaosOsc -B plugin/ChaosOsc/build
cmake --build plugin/ChaosOsc/build --config Release
ctest --test-dir plugin/ChaosOsc/build -C Release --output-on-failure
cmake --install plugin/ChaosOsc/build --config Release \
  --prefix "$HOME/Library/Application Support/SuperCollider/Extensions"   # Linux: "$HOME/.local/share/SuperCollider/Extensions"
```

Windows (PowerShell, from the repository root):

```powershell
cmake -S plugin/ChaosOsc -B plugin/ChaosOsc/build -A x64
cmake --build plugin/ChaosOsc/build --config Release
ctest --test-dir plugin/ChaosOsc/build -C Release --output-on-failure
cmake --install plugin/ChaosOsc/build --config Release --prefix "$env:LOCALAPPDATA\SuperCollider\Extensions"
```

Without `--prefix`, `cmake --install` stages into `<build>/install/ChaosOsc`.
The build defaults to `Release`; useful cache options:

| Option | Default | Meaning |
|---|---|---|
| `SC_PATH` | *(empty)* | SuperCollider source root whose `include/plugin_interface` and `include/common` headers to use; empty fetches the pinned 3.14.1 headers. |
| `CMAKE_OSX_ARCHITECTURES` | `arm64;x86_64` | macOS architectures. The universal default matches the official universal SuperCollider app (which can also run under Rosetta). |
| `CMAKE_OSX_DEPLOYMENT_TARGET` | `11.0` | Minimum macOS, matching the official SuperCollider 3.14.1 app. |
| `CHAOSOSC_WARNINGS_AS_ERRORS` | `ON` | `-Wall -Wextra -Werror` (MSVC `/W4 /WX`); SuperCollider headers are system includes. |
| `CHAOSOSC_BUILD_TESTS` | `ON` | Build the DSP-core unit test and register it with CTest. |

A manual `cmake --install` creates `ChaosOsc` without the installer's marker,
so the installer will later refuse to replace it unless you pass `--force`.

## Uninstall

```sh
python3 scripts/install_chaososc.py --uninstall   # removes only an installer-made folder
```

For a manual install, delete `<Extensions>/ChaosOsc`. Then recompile the class
library and reboot the server as above.

## Prebuilt CI artifacts

The *Plugin Builds* GitHub Actions workflow builds and tests ChaosOsc on
macOS (universal), Linux (x86_64), and Windows (MSVC x64), and uploads each
installed folder as an artifact (`ChaosOsc-macOS-universal`,
`ChaosOsc-Linux-x86_64`, `ChaosOsc-Windows-x64`). Unzip it and copy the
`ChaosOsc` folder into your Extensions directory, then recompile and reboot.
On Windows that workflow also renders ChaosOsc in SuperCollider 3.14.1's
`scsynth.exe` (non-realtime) as a smoke test.

## Troubleshooting

- **`ERROR: Class not defined.` / ChaosOsc is unknown in sclang:** recompile
  the class library. If it persists, check that the folder is inside
  `Platform.userExtensionDir.postln` (or another folder sclang compiles).
- **`UGen 'ChaosOsc' not installed` (in the server post window):** scsynth
  did not load the plugin. Reboot the server after installing (`s.reboot`).
  If you set `s.options.ugenPluginsPath`, it replaces the default plugin
  search path, so include the Extensions directory. The binary must be
  `ChaosOsc.scx` (macOS/Windows) or `ChaosOsc.so` (Linux) for your
  architecture (the macOS build is universal by default).
- **Duplicate copies:** two `ChaosOsc` folders (for example an old manual copy
  plus an installer copy, or one in the system Extensions directory) make
  sclang report a duplicate class and scsynth may load the wrong plugin. Keep
  exactly one; the installer prints a warning for each extra copy it finds.
- **macOS Gatekeeper blocks a downloaded binary** (for example a CI
  artifact): remove the quarantine flag, then reboot the server:

  ```sh
  xattr -dr com.apple.quarantine "$HOME/Library/Application Support/SuperCollider/Extensions/ChaosOsc"
  ```

  Locally built binaries are not quarantined.
- **Configure fails fetching headers (offline or behind a proxy):** retry
  online, or pass `--sc-path` / `-DSC_PATH=` pointing at a SuperCollider
  3.14.1 source checkout.
- **Configure says no C++ compiler was found:** install one of the compilers
  listed under *Requirements*, then delete the build directory and retry.
- **A manual build fails only on a new compiler warning:** reconfigure with
  `-DCHAOSOSC_WARNINGS_AS_ERRORS=OFF` (the installer already does this).
- **The installer refuses to overwrite `ChaosOsc`:** that folder has no
  installer marker, so it was not created by the installer. Remove it
  yourself or re-run with `--force`.

## Developer checks

`bash scripts/run_headless_tests.sh` (with `SCLANG`/`SCSYNTH` set) runs the
full gate, including `tests/test_chaososc_cmake_install.py`: the CMake
build/CTest/install layout, exported `load` symbol, universal macOS binary,
installer behaviors, and an end-to-end check that the *installed* folder
compiles in sclang (no `--include-path`) and renders in scsynth NRT mode.
