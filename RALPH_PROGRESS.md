Ralph-Status: IN_PROGRESS

## Iteration 1: ChaosOsc DSP core (first sound-design palette entry)

- **Environment finding:** `sclang`, `scsynth`, and any SuperCollider plugin
  build headers are not installed in this development environment, and no
  local `supercollider/` reference checkout is present in this worktree.
  This blocks building/testing an actual SC server plugin or sclang class
  this iteration. `clang++` (Apple clang 17.0.0) and `cmake` are available.
  Per the TDD skill's DSP guidance ("test pure DSP calculations ... where
  practical"), this iteration implements and tests the DSP core independent
  of the SC toolchain, and records the SC-side work as an explicit next task
  rather than claiming it.
- **Behavior under test:** the ChaosOsc logistic-map chaotic oscillator core
  must produce bounded (`[-1, 1]`), finite output; be deterministic for a
  fixed seed and `chaosAmount`; stay bounded/finite even for out-of-range
  `chaosAmount` inputs; and escape the map's degenerate fixed point when
  seeded exactly at it.
- **Red:** Wrote `plugin/ChaosOsc/Tests/test_chaos_osc_core.cpp` against a
  not-yet-created `plugin/ChaosOsc/Source/ChaosOscCore.hpp`, then ran:
  `clang++ -std=c++17 -Wall -Wextra -O2 plugin/ChaosOsc/Tests/test_chaos_osc_core.cpp -o plugin/ChaosOsc/Tests/test_chaos_osc_core_bin`.
  Result: compile failure —
  `fatal error: '../Source/ChaosOscCore.hpp' file not found`. This is a
  meaningful Red (the production code the test exercises does not exist yet),
  not a broken fixture or missing dependency.
- **Green:** Implemented `plugin/ChaosOsc/Source/ChaosOscCore.hpp` (header-only,
  dependency-free `chaososc::ChaosOscCore`). Re-ran the same compile command
  (exit 0), then ran the resulting binary. All 6 assertions passed:
  bounded/finite output over 100,000 samples; identical sequences for
  identical seed/`chaosAmount`; bounded/finite output for out-of-range
  `chaosAmount` (`10.0`, `-5.0`); escape from the fixed-point seed (`0.0`).
- **Refactor:** Extracted the build/run steps into
  `plugin/ChaosOsc/Tests/run_tests.sh` (build artifacts under a
  gitignored `.build/` dir) and removed the ad hoc build output. Re-ran
  `bash plugin/ChaosOsc/Tests/run_tests.sh`: all 6 assertions passed again
  (exit 0), confirming the refactor preserved behavior.
- **Documentation:** Added `plugin/SOUND_DESIGN.md` describing the ChaosOsc
  DSP, its planned sclang-facing controls (`chaosAmount`, `seed`, and a
  planned decoupled update-rate control), its real-time-safety rationale,
  and exactly what remains unverified (SC plugin build/load, sclang class,
  NRT render, real-time audition). Added `decision_log.md` entry DEC-010
  recording the palette choice and the environment-driven scope decision to
  build/test the DSP core before the SC plugin wrapper.
- **Regression check:** `bash -n scripts/ralph-loop.sh`,
  `bash -n tests/ralph-status-reporting.sh`, and `git diff --check` passed
  (no unrelated files touched; no trailing-whitespace/conflict-marker issues).
  `tests/ralph-status-reporting.sh` was not re-run this iteration because
  this change does not touch the runner/status-reporting workflow it covers.
- **Platform coverage:** Verified only on this development machine (macOS,
  Apple clang 17.0.0, arm64). Windows 10 x64 and an actual MacBook Neo are
  not verified. No SuperCollider plugin, sclang class, NRT render, or
  real-time audition exists yet, so those acceptance criteria remain
  unimplemented, not just unverified on other platforms.
- **Next task:** Verify/obtain a SuperCollider plugin build environment
  (source or SDK headers, `sclang`, `scsynth`), then write a failing SC-side
  test that loads the ChaosOsc plugin, calls it from an sclang class, and
  renders a short NRT `Score` to a WAV file, before implementing the
  `UGen` subclass and sclang class wrapping the now-tested
  `ChaosOscCore`. In parallel, begin phase-0 discovery on sclang's secure
  asynchronous HTTPS/credential-store options (`HTTPClient` or similar) so a
  headless helper's necessity can be decided.
