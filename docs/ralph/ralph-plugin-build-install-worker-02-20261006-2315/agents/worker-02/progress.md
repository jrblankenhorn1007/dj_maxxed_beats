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
(see below)
