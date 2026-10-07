# worker-03 progress — assistant GUI, packaging, CI, docs

Branch `ralph/ai-gui-packaging-worker-03-20261007` (base 961b1c2). Design:
[docs/design/gui.md](../../../../design/gui.md).

## Delivered

- GUI: `MaxxedBeats.gui` → `MBGuiWindow` (Qt) + `MBGuiController` (state) +
  `MBMaskedField`, `MBGuiFormat`, `MBGuiAudition`; one wiring factory
  `MaxxedBeats.services(lookup)` (classes looked up by name).
- Packaging: `extension/MaxxedBeats.quark`, help (`MaxxedBeats.schelp`,
  `Guides/MaxxedBeats-Assistant.schelp`), `scripts/install_maxxedbeats.py`.
- CI: `.github/workflows/assistant-tests.yml` (macOS 14 + Windows; pinned SC
  3.14.1 with SHA-256; installer install → `test_mb_*.py` → uninstall).
- Docs: `docs/USER_GUIDE.md`, README, `docs/design/gui.md`,
  `docs/VISUAL_TEST_PLAN.md` tooling section.

## TDD evidence

- Red: `tests/test_mb_gui.py` failed with "Class not defined" before the GUI
  classes existed; `tests/test_mb_install.py` failed on the missing module.
- Green: GUI state script ≈170 checks, entry/factory/help script 40+ checks,
  15 installer tests, 6 workflow contract tests.
- Regression checks added after visual review: `&&` tab label, progress reset
  per operation, short masked-key label.

## Local verification (MacBook Neo, macOS 26 arm64, SC 3.14.1, Python 3.9)

- `SCLANG=… python3 -m unittest tests.test_mb_gui tests.test_mb_install tests.test_mb_install_workflow` → OK.
- Real installer run into `tests/.build/mb-install/real/Extensions` (CMake
  build of ChaosOsc, Quark copy, markers) and `--uninstall` → both removed.
- Visual (support tooling, not sign-off): `python3 tests/mb_gui/capture_screenshots.py`
  captured 10 native-window screenshots (sclang launch, fake services) to
  `tests/.build/mb-gui-screens/run3/`; inspected 01/03/04/06/07/08/09/10:
  layout legible, no clipping; defects found and fixed (see above). SCIDE
  launch with the real mock provider and NRT render, and Windows 10, remain
  open.
- Full gate: see final report.

## Notes

- During the first Red run a hung sclang was killed by PID without filtering
  by worktree; the PID belonged to worker-01's test run (one test run lost).
  All later process handling uses harness timeouts only.
