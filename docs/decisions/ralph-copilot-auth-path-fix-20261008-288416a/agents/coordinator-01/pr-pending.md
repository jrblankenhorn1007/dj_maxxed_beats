# Copilot auth-home fix — implementation record (PR pending)

- **Run/task:** `copilot-setup-onboarding-20261007-1640` /
  `copilot-runtime-setup-onboarding`
- **Branch:** `ralph/copilot-auth-path-fix-20261008-288416a`
- **Worktree:** `/Users/jrblankenhorn/dj_maxxed_beats.worktrees/ralph-copilot-auth-path-fix-20261008-288416a`
- **Base `origin/main`:** `288416aa955a270cf0167593bbe54005743c6b81`
- **Project decision:** [DEC-046](../../../../decision_log.md#dec-046--preserve-the-users-copilot-authentication-home)
- **Implementation commit:** `6bcf922ade7ef988cc017969cec92c8bb6f7d518`
- **Pull request:** not opened

## Root cause and decision

The bridge passed a temporary request directory as
`CopilotClient.base_directory`. The SDK uses that setting for `COPILOT_HOME`,
so the active SCIDE process looked for the user's saved Copilot login in the
temporary folder. Removing the override lets the SDK use its documented
default user home; per-request workspace/config isolation remains on the
session, and tool denial is unchanged.

## Verification before publication

- Test-first regression: the focused bridge test failed before the production
  change because `base_directory` was the per-request directory.
- Green regression test: passed with the private Python 3.14.8 runtime.
- Focused repository Copilot bridge/setup suite: **35 tests passed, 1 skipped**.
- Branch bridge auth probe with SCIDE's system-only `PATH`: authenticated
  successfully using the user's existing saved login.
- Full repository headless gate: **237 tests passed, 7 skipped** in
  **242.434 seconds**.
- `git diff --check`: passed.

## Acceptance still open

The live probe used the branch bridge directly, not the installed file in the
active SCIDE extension. In-window model refresh and a real GUI request have not
yet been verified. Physical Windows 10 x64 visual acceptance also remains
open. No end-to-end completion claim is made.
