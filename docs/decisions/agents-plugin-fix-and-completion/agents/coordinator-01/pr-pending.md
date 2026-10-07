# Coordinator decisions — `agents/plugin-fix-and-completion`

- **Branch:** `agents/plugin-fix-and-completion` (parent; session worktree
  `/Users/jrblankenhorn/dj_maxxed_beats.worktrees/plugin-fix-and-completion`)
- **Base:** `origin/main` `1b9a1ef4d5f66f8e81d5e1af3caece628755e8c1`
- **Agent:** `coordinator-01` (VS Code Copilot session
  `copilotcli:/e4c778d9-98e0-4865-93f2-cd74161f56ff`)
- **PR:** pending (parent-to-main integration is PR-only under the `Gate`
  ruleset)

## D1 — Interpret "fix/finish this plugin" as a complete, installable ChaosOsc

- **Context:** All 32 existing headless tests passed on the base, but the
  plugin could only be built by a test-only smoke script, had no install
  path, no real-time verification, an unimplemented planned rate control,
  and a help file that SCDoc could not parse.
- **Alternatives:** documentation-only status refresh; DSP-only changes;
  the whole Quark/GUI product.
- **Decision:** Fix the help-file defect, implement the planned iteration-rate
  control with `.kr`/`mul`/`add`, add a CMake build and installer with an
  installed-layout end-to-end test, add cross-platform CI builds, and verify
  real-time operation. The Quark GUI/provider product remains out of scope.
- **Consequences:** "Working" is evidenced by a real install into a
  SuperCollider Extensions layout, NRT and real-time runs on SuperCollider
  3.14.1, and CI builds on three operating systems.

## D2 — Fix the SCDoc help syntax error test-first

- **Context:** `ChaosOsc.schelp` line 10 used a bare `::` before the
  constructor example. SCDoc 3.14.1 reported
  `syntax error, unexpected ::, expecting end of file`, so the help page
  never rendered.
- **Decision:** Add `tests/test_chaososc_help_scdoc.py`, which parses every
  ChaosOsc `.schelp` with the real `sclang` SCDoc parser; confirm Red;
  replace the bare markup with `code::...::`; confirm Green.
- **Evidence:** Red `SCDOC_PARSE_FAILURES: 1` with the line-10 syntax error;
  Green `Ran 3 tests ... OK` with the language-contract tests. Commit
  `fa6decd2daaec8d5c4c22d947efaeef61804a743`.

## D3 — Parallel in-host workers despite Resource Manager capacity

- **Context:** The Resource Manager reported `max_agents: 1`
  (`available memory is below the degraded threshold`, 2.64 GiB free of
  8 GiB). The owner explicitly asked for parallel subagents.
- **Decision:** Follow the owner's explicit instruction and run three
  in-host task subagents (no separate OpenCode processes) with disjoint
  worktrees and owned paths; avoid concurrent real-time audio work outside
  worker-03.
- **Consequences:** Local load is limited to each worker's builds and
  SuperCollider test processes; no reservation was fabricated.

## D4 — Streamlined process for cost and latency

- **Context:** The owner objected to coordinator time spent reading process
  documentation. The agent-sync ledger would require additional status-only
  PRs because GH013 rejects direct `main` writes, and the stale
  `djmb-platforms-sound-library-20260925-1439/coordinator-01` record (session
  `copilotcli:/d0f1b531-19ef-4644-92f9-2b17966bcb95`, archived and idle since
  2026-09-25T16:34:54Z) overlaps README/status documentation paths.
- **Decision:** Use general-purpose workers with self-contained assignments
  instead of the Ralph Loop profile, integrate children into the parent
  locally (child review `NOT_APPLICABLE`), and keep the independent review
  gate for the parent PR. Do not publish agent-sync status PRs for this run
  and do not edit the stale archived record; its worktree's uncommitted
  changes are left untouched.
- **Consequences:** Fewer PRs and less CI churn; this run's ownership is
  documented here and in the branch Ralph records instead of the ledger.

## D5 — Act on review round 1 before publication

- **Context:** The `Gate` ruleset applies to all branches and rejects updates
  to a published branch (GH013), so review ran on the unpublished head
  `f68bcd9` (base `1b9a1ef`). Code review found two blocking issues (an
  installed extension broke `scripts/render_composition.py` with a duplicate
  `ChaosOsc` class; installer removal chmod followed symlinks) and two
  non-blocking ones; security review found three LOW issues (PR-run artifacts,
  the same chmod defect, and an unescaped device name reaching `/bin/sh` in the
  opt-in real-time test).
- **Decision:** `FIX_MANUALLY` — fix all seven test-first: isolate the
  renderer's sclang user directories, re-raise POSIX removal failures without
  chmod, upload artifacts only from non-PR runs and document trusted
  downloads, reject shell-significant device names, follow symlinks with cycle
  protection in the duplicate scan, and correct the sound-design status.
- **Evidence:** each new test failed first for the reported reason; the full
  gate then passed `Ran 98 tests … OK` with the real-time opt-in.
