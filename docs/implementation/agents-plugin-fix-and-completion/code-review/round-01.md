# Review round 1 — pre-publication

- **Base:** `1b9a1ef4d5f66f8e81d5e1af3caece628755e8c1`
- **Head:** `f68bcd9cf9263e0e58960f86335d32f4b27e0d91`
- **Prompt (summary):** read-only review of `git diff 1b9a1ef..f68bcd9` per the
  Ralph reviewer definitions and PR Review skill; code reviewer focused on
  DSP/wrapper correctness, class, CMake/installer, CI, tests, and docs
  accuracy; security reviewer on the installer, CMake fetch, CI downloads and
  permissions, subprocess helpers, real-time test, and audio-thread safety.

## Ralph Code Reviewer — CHANGES_REQUESTED

- **R1 (blocking, medium):** installing ChaosOsc into the user Extensions
  folder made `scripts/render_composition.py` fail with
  `duplicate Class found: 'ChaosOsc'` (reproduced with a scratch HOME).
- **R2 (blocking, medium):** installer removal error handler chmodded
  `0o200` through symlinks, changing a file outside the install.
- **R3 (non-blocking, low):** duplicate-copy scan did not follow symlinked
  folders that sclang follows.
- **R4 (non-blocking, low):** `docs/plugin/SOUND_DESIGN.md` still called
  real-time/MacBook Neo unverified.

## Ralph Security Reviewer — CHANGES_REQUESTED (all LOW)

- **S1:** Plugin Builds uploaded installable artifacts from `pull_request`
  runs; the guide told users to unquarantine "the" CI artifact.
- **S2:** same defect as R2 (reproduced: outside file became `--w-------`).
- **S3:** the opt-in real-time test passed a `system_profiler` device name to
  `ServerOptions.device`, which `Server:boot` sends unescaped through
  `/bin/sh`.

## Author action — `FIX_MANUALLY`

All seven fixed test-first in `374db4e` (renderer language-home isolation,
POSIX removal re-raises without chmod, symlink-following duplicate scan with
cycle protection, corrected status, non-PR artifact upload plus guidance,
device-name validation). Gate: `Ran 98 tests … OK` with the real-time opt-in.
