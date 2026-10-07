# Coordinator handoff — Copilot setup onboarding

## 2026-10-07 — Iteration 1

- **Scope:** make the installed Copilot CLI discoverable outside SCIDE's
  inherited `PATH`; save its path and a private Python 3.11+ SDK runtime;
  refresh configuration in an already-running SCIDE; package one-click setup,
  launch, and uninstall paths; document the browser sign-in workflow.
- **Implementation:** per-user native CLI discovery on macOS/Linux/Windows;
  setup helper with pinned SDK and non-secret path configuration; executable
  macOS/Linux setup launchers; Windows `.cmd` wrappers and WinGet bootstrap;
  `LaunchMaxxedBeats.scd`; package and install tests.
- **Verification:** local full gate passed 228 tests with five platform or
  opt-in skips. Windows PowerShell package-script tests are reserved for the
  Windows CI job.
- **Open environment coverage:** no live Copilot sign-in/generation was
  attempted; Python 3.11+ is not installed in this local environment.
  Windows GUI behavior on physical Windows 10/11 remains unverified.
- **Integration:** PR not opened yet; no merge or `origin/main` update is
  claimed.
