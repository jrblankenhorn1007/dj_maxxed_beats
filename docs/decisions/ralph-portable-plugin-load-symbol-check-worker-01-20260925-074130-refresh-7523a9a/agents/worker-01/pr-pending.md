# Worker decision record — portable plugin load-symbol check

- **Run/task:** `ralph-cross-platform-finish-20260925-0607` /
  `portable-plugin-load-symbol-check`
- **Worker:** `worker-01 / portable ChaosOsc symbol check (fresh-main continuation)`
- **Iteration:** `2`
- **Branch:** `ralph/portable-plugin-load-symbol-check-worker-01-20260925-074130-refresh-7523a9a`
- **Worktree:** `/Users/jrblankenhorn/dj_maxxed_beats.worktrees/ralph-portable-plugin-load-symbol-check-worker-01-20260925-074130-refresh-7523a9a`
- **Starting `origin/main`:** `7523a9a0b87ffc5304686e2e64509fc4a6941bb7`
- **Coordinator-assigned base before refresh:** `1926bdab3c358088f359cf73f0d8025a66c7d0d0`
- **Implementation commit:** `4cb936134e7ccef09c248de7fe761783891fa6ec`
- **PR:** Pending first publication; number, URL, and current PR base/head are not yet available.

## Decision — carry the validated behavior on a fresh base

- **Context:** Prior PR #21 remains open with base
  `9c8c1b679b765ace2b4ae1dac49c1ed827f43171` and head
  `54153d6591e0e263674e1806e055260179db81c7`; it is stale relative to the
  new branch base. Its later status-record push was rejected with GH013:
  “Code coverage checks require merging via API or UI.” The active `Gate`
  ruleset `23973625` remains enabled.
- **Alternatives:** Retry or amend the old published branch; bypass or weaken
  the active ruleset; abandon the cross-platform check; or preserve the old
  PR/worktree and carry the scoped change on a fresh branch from fetched
  `origin/main`.
- **Decision:** Preserve PR #21, its branch, and its worktree without further
  edits. Create this fresh continuation branch from the refreshed
  `origin/main` SHA `7523a9a0b87ffc5304686e2e64509fc4a6941bb7`; do not
  bypass the ruleset or retry a rejected direct push.
- **Rationale:** The fresh branch includes the latest status/integration
  changes, avoids rewriting or disturbing a published stale branch, and keeps
  the approved scope isolated.
- **Consequences:** PR #21's GH013 event is a recovered integration issue,
  not a product blocker. The normal PR/review process remains required.

## Decision — verify the exact platform-specific loader entry point

- **Context:** The old check assumed Darwin `nm -gU` and `_load`. ELF and
  Windows x64 require `nm -g --defined-only` and `load`; substring or
  name-only checks can misidentify similar or undefined symbols.
- **Alternatives:** Accept either spelling on every platform, search by
  substring, skip type/global checks, fail if `nm` is absent, or keep the
  Darwin-only implementation.
- **Decision:** Select platform-specific flags and expected symbol; require
  the exact global defined `T` entry point, trim trailing CR from symbol
  output, report `nm` failure status/diagnostics, and preserve the existing
  warning-and-skip path when `nm` is absent. Add network-free mocks for
  Darwin, ELF, Windows x64/CRLF, similar and undefined names, command
  failure, and missing `nm`; make the NRT check accept exactly one of the
  two valid verification lines.
- **Rationale:** This detects the actual ABI loader entry point and separates
  symbol absence from a failed inspection without converting optional `nm`
  into a new hard prerequisite.
- **Consequences:** The local Darwin arm64 build and SuperCollider 3.14.1 NRT
  run passed. ELF/Windows behavior is mocked only; no native Windows 10 x64
  or ELF validation is claimed. Product implementation iteration remains
  `5`.

## Verification and outstanding gates

- TDD Red: 5 of 8 mocked tests failed against the unchanged Darwin-only
  implementation, for expected platform/diagnostic behavior.
- Green/refactor: all 8 mocked regression tests passed; Bash syntax and
  `git diff --check` passed.
- Native macOS smoke build verified `_load`; SuperCollider 3.14.1 NRT and the
  final headless pipeline passed (9 DSP assertions and 21 Python tests).
- Native ELF, Windows 10 x64, actual MacBook Neo, GUI/SCIDE, and real-time
  audition remain unverified.
- **Unresolved product blockers:** none for this bounded task.
- **PR/review:** not yet created; once opened, this pending record must be
  moved to the numbered PR file and populated with the exact PR base/head.
- **Merge:** not authorized or attempted. Await the coordinator's independent
  code and security reviews and explicit authorization.
- **Memory:** coordinator post-merge Project Memory review is still pending;
  no pre-merge shared-memory update is warranted.
