# Agent / PR record — coordinator-01 — PR #41 open

- **Run/task:** `copilot-setup-onboarding-20261007-1640` /
  `copilot-runtime-setup-onboarding`
- **Coordinator:** `coordinator-01 / Copilot setup onboarding`
- **Runtime/session ID:** `copilotcli:/e4c778d9-98e0-4865-93f2-cd74161f56ff`
- **Branch:** `ralph/copilot-windows-onboarding-20261007-1640`
- **Base `origin/main`:** `dac46c31f6711ad0d90d40b9634ba92aa5a0203b`
- **Current implementation commit:** `cab1f464346953e6a39b4477125de0c8bcc6a078`.
- **Pull request:** [#41](https://github.com/jrblankenhorn1007/dj_maxxed_beats/pull/41),
  base `dac46c31f6711ad0d90d40b9634ba92aa5a0203b`, current PR head
  `f8f400a45297e39b02434d4fc3d665a49889c964`.
- **Review:** round 2 reviewed this exact head; security found no
  vulnerabilities, and the code review's Ubuntu 22.04 APT/Python fallback
  finding is fixed locally. A stacked PR and targeted remediation confirmation
  are pending.
- **Merge:** not attempted; no `origin/main` integration is claimed.

## Decision

- **Context:** The official Copilot CLI was installed in a per-user directory,
  but SCIDE's process environment did not include that directory on `PATH`.
  The system Python on this machine is below the Copilot SDK's Python 3.11
  minimum. Copilot subscription access belongs to the official CLI's browser
  sign-in flow, not an API-key text field.
- **Decision:** Discover supported per-user native CLI locations, set up a
  private pinned SDK environment, save only executable paths in
  SuperCollider's per-user settings directory, and reload that configuration
  for each provider request. Provide double-click platform helpers and include
  the Windows setup/launch/uninstall wrappers in the ready-made zip.
- **Alternatives:** Ask users to edit `PATH`/runtime JSON, install Python and
  SDK dependencies manually, or add a Copilot API-key field.
- **Rationale:** SCIDE cannot rely on an interactive shell's `PATH`; explicit
  runtime paths plus the official browser flow remove shell setup and avoid
  handling Copilot credentials in MaxxedBeats.
- **Consequences:** Copilot still needs Python 3.11+ and the official CLI.
  Windows setup uses WinGet; macOS/Linux setup downloads the pinned official
  CLI release and verifies its SHA-256 before installing the executable.
  Unit tests use fakes; no live sign-in or generation is claimed.

## Verification

- `SCLANG=/Applications/SuperCollider.app/Contents/MacOS/sclang SCSYNTH=/Applications/SuperCollider.app/Contents/Resources/scsynth bash scripts/run_headless_tests.sh`
  — **PASS**, 228 tests, five platform/opt-in skips.
- The implementation commit passed `git diff --cached --check`; final status
  records also pass staged whitespace, YAML/status synchronization, and local
  Markdown-link checks. Hosted Windows CI remains pending.
- Hosted CI first ran on PR #41. At initial inspection, the Linux ChaosOsc
  build passed and the other Windows/macOS/headless checks were pending or in
  progress; all original-head PR #41 checks subsequently passed. Round-1
  reviewers found a mutable shell-pipe installer (HIGH), incomplete macOS
  Python discovery (MEDIUM), and a Linux no-terminal prompt path (MEDIUM).
  Those findings are fixed locally and covered by the passing 232-test gate.
  The first stacked fix PR exposed two Windows-only test assumptions; the
  test-only correction passes locally (14 setup tests, one Windows-only skip)
  and replacement PR #43 merged into #41 at `f8f400a`. All hosted checks pass
  on that exact head. Round-2 review then found and fixed the Ubuntu 22.04 APT
  fallback issue in `cab1f464`; the APT fallback regression and all setup
  tests pass locally. Its stacked PR and targeted remediation confirmation
  remain pending.
- Local Windows PowerShell package-script tests are unavailable; they are
  expected to run in the hosted Windows Assistant Tests workflow.
