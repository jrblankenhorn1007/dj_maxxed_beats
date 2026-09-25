# Worker-01 progress — headless test pipeline

## Iteration 1 — IN_PROGRESS

- **Run/task:** `headless-integration-tests-20260925-0246` /
  `implement-headless-test-pipeline`.
- **Worker:** `worker-01 / headless test pipeline`; runtime agent/session ID
  unavailable (`null`).
- **Branch/worktree:** `ralph/headless-integration-tests-worker-01-20260925-0246`
  at `/Users/jrblankenhorn/dj_maxxed_beats.worktrees/ralph-headless-integration-tests-worker-01-20260925-0246`.
- **Base:** fetched `origin/main` at
  `0736add11eae7b7f745d7b7bf9806c116d72eed6`; no rebase has been needed.
  The main integration worktree at `/Users/jrblankenhorn/dj_maxxed_beats`
  was clean and attached to `main`.
- **Scope:** add one mandatory headless C++/Python/NRT test entrypoint and a
  macOS GitHub Actions workflow using the official SuperCollider 3.14.1 CLI
  binaries; update the user-facing automated/visual test distinction and
  project verification records. No product behavior or GUI was changed.

### TDD evidence

- **Red:** Before adding the entrypoint/workflow,
  `PYTHONDONTWRITEBYTECODE=1 python3 tests/test_headless_test_pipeline.py`
  ran 3 tests and failed as expected because
  `scripts/run_headless_tests.sh` and
  `.github/workflows/headless-tests.yml` were missing.
- **Green:** After implementation,
  `PYTHONDONTWRITEBYTECODE=1 python3 tests/test_headless_test_pipeline.py`
  passed all 3 contract tests. The first attempt exposed a test-fixture
  assumption (`/bin/true` is not available on this host); using
  `shutil.which("bash")` as a known executable fixed the fixture, and the
  same command passed.
- **Refactor:** Extracted repeated required-file checks/reads into
  `_read_required_file`. Re-ran
  `PYTHONDONTWRITEBYTECODE=1 python3 tests/test_headless_test_pipeline.py`;
  all 3 tests passed.

### Runtime and full-pipeline evidence

- Downloaded the official DMG to ignored `.runtime/` from
  `https://github.com/supercollider/supercollider/releases/download/Version-3.14.1/SuperCollider-3.14.1-macOS-universal.dmg`.
  Verified SHA-256
  `ed264b32752d27fc86e506dd0a7eb36de7c19ebce73c3fdf2ed5514f8c73f02e`,
  mounted with `hdiutil attach -readonly -nobrowse -noautoopen`, and checked
  that `sclang`/`scsynth` report 3.14.1 release commit `426edf6`.
- `bash -n scripts/run_headless_tests.sh` — passed.
- `ruby -e 'require "yaml"; YAML.load_file(".github/workflows/headless-tests.yml"); puts "YAML syntax: OK"'` — passed.
- `git diff --cached --check` — passed.
- `SCLANG=.runtime/mount/SuperCollider.app/Contents/MacOS/sclang SCSYNTH=.runtime/mount/SuperCollider.app/Contents/Resources/scsynth bash scripts/run_headless_tests.sh` — passed: all 9 DSP C++ assertions and all 12 Python tests, including the real ChaosOsc NRT plugin/class load and render (`Ran 12 tests in 86.724s`, `OK`).
- With ignored symlinks under `.runtime/bin` to the same two CLI executables,
  `env -u SCLANG -u SCSYNTH PATH="$PWD/.runtime/bin:$PATH" bash scripts/run_headless_tests.sh` — passed: all 9 DSP assertions and all 12 Python tests, including NRT (`Ran 12 tests in 16.557s`, `OK`).
- After tightening the contract test to require the `test_*.py` discovery
  pattern, the explicit-path command
  `SCLANG=.runtime/mount/SuperCollider.app/Contents/MacOS/sclang SCSYNTH=.runtime/mount/SuperCollider.app/Contents/Resources/scsynth bash scripts/run_headless_tests.sh`
  passed all 9 DSP assertions and all 12 Python tests, including NRT
  (`Ran 12 tests in 90.531s`, `OK`).
- The NRT integration and local pipeline used macOS 26.5.2 arm64. No SCIDE,
  GUI, real-time server, or audio hardware was launched. The GitHub workflow
  is configured for `macos-14`, pull requests, pushes, and manual dispatch;
  its hosted execution is not claimed by the local checks. The pipeline
  makes no Windows coverage claim.
- `docs/RALPH_PROGRESS.md` records the same exact TDD and full-pipeline
  commands/results; DEC-025 records the pipeline/visual-test boundary.

### Integration and sign-off

- **Pull request:** pending branch publication.
- **Merge:** not attempted; worker remains subject to coordinator
  authorization. No remote-main merge is claimed.
- **Current next action:** complete staged-diff review, publish/open the PR,
  update this leaf and decision record with the PR number, then report
  `AWAITING_MERGE`.
