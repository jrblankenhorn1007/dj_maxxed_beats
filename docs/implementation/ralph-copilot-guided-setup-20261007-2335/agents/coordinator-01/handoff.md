# Coordinator handoff — Copilot setup diagnostics

## 2026-10-07 — Follow-up iteration

- **Root cause:** the installed Copilot helper already installs or guides users
  through Python, the pinned SDK, and the official CLI, but the Python-version
  error shown by MaxxedBeats named only the requirements. It did not identify
  the correct macOS, Linux, or Windows setup launcher, leaving Git
  authorization easy to confuse with runtime setup.
- **Implementation:** the bridge now directs macOS users to
  `setup-copilot.command`, Linux users to run `setup-copilot.sh` in Terminal,
  and Windows users to `Setup-Copilot.cmd`. The same helper guidance is used
  for missing SDK and CLI configuration errors. The user guide explicitly
  separates Git authorization from Copilot runtime setup and sign-in.
- **Red:** the new platform-guidance test failed on the old bridge message,
  which omitted `setup-copilot.command`.
- **Verification:** the platform-specific bridge tests pass for all three
  operating systems. The SuperCollider provider integration test confirms the
  launcher name reaches the error callback. The focused Copilot/setup/install
  suite passed 58 tests with four skips; the full headless gate passed 236
  tests with six skips.
- **Remaining gaps:** the Mac currently has Python 3.9.6, so live Copilot
  setup, browser sign-in, and generation remain unverified. Physical
  Windows 10 x64 and MacBook Neo visual acceptance also remain open.
*** End of File
