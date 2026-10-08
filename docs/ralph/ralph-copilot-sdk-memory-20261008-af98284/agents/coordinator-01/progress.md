# Copilot SDK runtime memory follow-up

## Post-merge review and update — 2026-10-08

- **Run/task:** `copilot-setup-onboarding-20261007-1640` /
  `copilot-runtime-setup-onboarding`; coordinator `coordinator-01`.
- **Branch/worktree:** `ralph/copilot-sdk-memory-20261008-af98284` /
  `/Users/jrblankenhorn/dj_maxxed_beats.worktrees/ralph-copilot-sdk-memory-20261008-af98284`.
- **Base:** fresh worktree from fetched `origin/main` at
  `af9828452017d9379f505adcf890342d838d3b7f`.
- **Memory content commit:** `3299e83876bb0e0fb40900d5d9b8226512b4c30d`.
- **Parent implementation:** PR #50, base
  `1871b5bc9a18951185efa2103dd89e375081007d`, head
  `00b2e80ae1aaae5338de97515d2a4cc5d721f5c5`, merge
  `af9828452017d9379f505adcf890342d838d3b7f`.
- **Memory review:** read the current Project Memory skill and the project's
  `.github/memory/README.md`, `runtime-setup.md`, and `git-workflow.md`.
  The runtime category had no SDK-managed-protocol-runtime lesson.
- **Durable lesson:** use the SDK's version-matched protocol runtime for SDK
  connections and reserve the companion interactive CLI for login. The
  verified root cause, SDK 1.0.16/CLI 1.0.93 behavior, regression tests, and
  successful installed-provider run support the rule. Added it to
  `.github/memory/runtime-setup.md`.
- **Documentation-only checks:** TDD Red/Green/Refactor is not applicable.
  Final `git diff --cached --check` passed across the complete status, dossier,
  and memory follow-up change set.
- **Prior branch review/merge/install:** see the PR #50 record and iteration
  11 project progress entry.
- **Post-merge integration:** this memory update requires its own PR and
  verification on fetched `origin/main`. SCIDE visual acceptance and physical
  Windows 10 x64 visual acceptance remain open for the broader project.
