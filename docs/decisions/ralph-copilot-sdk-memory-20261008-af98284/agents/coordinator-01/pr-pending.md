# Branch memory follow-up decision record — PR pending

- **Run/task:** `copilot-setup-onboarding-20261007-1640` /
  `copilot-runtime-setup-onboarding`
- **Coordinator:** `coordinator-01 / Copilot SDK runtime memory follow-up`
- **Branch:** `ralph/copilot-sdk-memory-20261008-af98284`
- **Worktree:** `/Users/jrblankenhorn/dj_maxxed_beats.worktrees/ralph-copilot-sdk-memory-20261008-af98284`
- **Base `origin/main`:** `af9828452017d9379f505adcf890342d838d3b7f`
- **Implementation commit:** `3299e83876bb0e0fb40900d5d9b8226512b4c30d`
  (memory lesson; status/evidence commit pending).
- **Pull request:** expected after all status and memory changes are committed;
  number not yet assigned.
- **Parent PR #50:** merged and verified at
  `af9828452017d9379f505adcf890342d838d3b7f`.

## Memory decision

Add a concise runtime-setup lesson: use an SDK's version-matched managed
protocol runtime for SDK operations and reserve its separate interactive CLI
for authentication. Keep the lesson grounded in the Copilot handshake
failure, regression tests, full CI, and installed default-provider smoke test.

## Alternatives

No memory update would leave a verified, reusable SDK/runtime distinction
undocumented. Adding the rule to testing or git workflow would duplicate
existing categories; `runtime-setup.md` is the primary category.

The full review, merge, and memory-update verification record will be
completed after integration.
