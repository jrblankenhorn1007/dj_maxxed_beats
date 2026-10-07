# worker-02 progress — ChaosOsc CMake build, installer, CI builds

Branch: `ralph/plugin-build-install-worker-02-20261006-2315` (base `fa6decd`).
Host: macOS 26.5.2 arm64, Apple clang 17, CMake 4.4.3, Python 3.9.6,
SuperCollider 3.14.1 (official universal app, mounted read-only).

## TDD log

### Red
- `PYTHONWARNINGS=error python3 -m unittest tests.test_chaososc_install_scripts tests.test_chaososc_cmake_install`
  → `FAILED (errors=6)`: `CMake Error: The source directory ".../plugin/ChaosOsc" does not appear to contain CMakeLists.txt`,
  and `FileNotFoundError: .../scripts/install_chaososc.py` (also `ci_verify_plugin.py`, `ci_nrt_smoke.py` missing).
- Quality-check coverage test → `FAILED (failures=3)`: `'scripts/install_chaososc.py' not found in` run_quality_checks.sh (same for the two CI helpers).
- Workflow contract test with `plugin-builds.yml` moved aside → `FAILED (failures=2)`: `missing .../plugin-builds.yml`.
- Smoke-helper report-file protocol (Windows stdout-buffering hardening) → `TypeError: build_score_source() got multiple values for argument 'windows'` (new `report_path` parameter not implemented yet).

### Green
- Same unittest command → `Ran 38 tests ... OK` (first green), then 42 tests incl. the
  fail-fast "class not installed" E2E case, then `Ran 25 tests ... OK` after the report-file change.
- Full gate `SCLANG=... SCSYNTH=... bash scripts/run_headless_tests.sh` → `Ran 75 tests in 157.971s OK`
  (33 pre-existing + 42 new), wall time 3m04s.

### Evidence gathered while implementing
- SC 3.14.1 `SC_Filesystem_macos.cpp` (pinned commit) honors `XDG_DATA_HOME` on macOS before
  `~/Library/Application Support`; confirmed empirically with sclang (`Platform.userExtensionDir`).
  The installer mirrors this; the E2E test unsets XDG vars so the macOS default path is exercised.
- Official SC 3.14.1 macOS binaries are universal with `minos 11.0` → CMake defaults
  `CMAKE_OSX_ARCHITECTURES=arm64;x86_64`, `CMAKE_OSX_DEPLOYMENT_TARGET=11.0` when unset.
- CMake build: `lipo -info` → `x86_64 arm64`; `otool -l` → `minos 11.0` ×2; `nm -gU` → only
  `_api_version`, `_load`, `_server_type` (hidden visibility, like the official plugins).
- `SuperCollider-3.14.1-win64.zip` sha256 verified locally = `a5f95416…58cd`; layout is
  `SuperCollider/{sclang.exe,scsynth.exe,plugins/,vcruntime140*.dll,...}`. The PE export parser in
  `scripts/ci_verify_plugin.py` reads the official MSVC plugins (`OscUGens.scx`, `BinaryOpUGens.scx`)
  as machine `0x8664` exporting `api_version, load, server_type` (matches `objdump -p`).
- sclang waits in its REPL forever when a script fails to compile (probe timed out at 20 s), so the
  smoke helper guards the class at run time and fails in <1 s when ChaosOsc is not installed.
- Real user Extensions dir (`~/Library/Application Support/SuperCollider/Extensions`) checked empty
  before and after all runs; every test uses an isolated HOME and explicit `--extensions-dir`.

## CI runs

Each attempt is pushed as a new branch from the current commit (the ruleset forbids
updating pushed branches).

### Attempt 1 — `ralph/plugin-build-install-worker-02-20261006-2315-ci1` @ `a773b82`
- Plugin Builds run `37548968452`: **success** on all three jobs
  (https://github.com/jrblankenhorn1007/dj_maxxed_beats/actions/runs/37548968452)
  - macOS-14 (AppleClang 15, CMake 4.4.3): CTest 100%; `nm _api_version, _load, _server_type`;
    `lipo: arm64 x86_64`; installer round trip into `/Users/runner/Library/Application Support/SuperCollider/Extensions`.
  - ubuntu-latest (GCC 13.3, CMake 3.31.6): CTest 100%; `nm: api_version, load, server_type`;
    installer round trip into `/home/runner/.local/share/SuperCollider/Extensions`.
  - windows-latest (Visual Studio 18 2026, MSVC 19.51, `-A x64`, `/W4 /WX`, 0 compiler warnings):
    CTest 100%; PE export table (x64) and `dumpbin /exports` both list `api_version, load, server_type`;
    SC 3.14.1 win64 zip sha256 `OK`; installer → `C:\Users\runneradmin\AppData\Local\SuperCollider\Extensions\ChaosOsc`;
    sclang `Platform.userExtensionDir` matched and compiled the class from there; `scsynth.exe -N`
    render OK (24064 frames @ 48 kHz, rms 0.0621, peak 0.0950 — identical to macOS); uninstall OK.
  - Artifacts: `ChaosOsc-macOS-universal`, `ChaosOsc-Linux-x86_64`, `ChaosOsc-Windows-x64`.
- Headless Tests run `37548968466` (macOS-14, SC 3.14.1 DMG): **success**, `Ran 76 tests ... OK`
  including the new CMake/installer/E2E tests.
- Finding from the macOS log: the verifier printed one un-sliced `nm` line, because Apple's llvm-nm
  lists only the host slice of a universal binary by default. Red: new unit test
  `test_macos_export_check_inspects_every_architecture_slice` failed with
  `[['nm', '-gU', 'ChaosOsc.scx']] != [['nm', '-gU', '-arch', 'all', 'ChaosOsc.scx']]`.
  Green: the verifier and the build test now use `nm -gU -arch all` and require `_load` in both
  the arm64 and x86_64 slices (verified locally: `Verified nm [arm64]` / `Verified nm [x86_64]`;
  a thinned arm64-only copy fails `--require-universal`).
