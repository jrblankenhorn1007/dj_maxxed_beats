# Worker 01 — pull request pending

- **Run/task:** `ralph-cross-platform-finish-20260925-0607` /
  `portable-plugin-load-symbol-check`
- **Worker:** `worker-01 / portable ChaosOsc symbol check`
- **Runtime session:** `copilotcli:/a17ae5a3-53fe-4381-a9fd-f590086cec29`
- **Branch:** `ralph/portable-plugin-load-symbol-check-worker-01-20260925-0607`
- **Worktree:** `/Users/jrblankenhorn/dj_maxxed_beats.worktrees/ralph-portable-plugin-load-symbol-check-worker-01-20260925-0607`
- **Base `origin/main`:** `c448dae05f792ef868557e7d67a0a1becb7e6895`
- **Implementation commit:** Pending.
- **Pull request:** Pending; the authorized workflow is a normal direct
  worker-owned PR. This record will be renamed to `pr-<number>.md` and the
  branch index updated when GitHub assigns the PR number.
- **Merge:** Not authorized or attempted. Coordinator authorization for this
  exact PR is required before any merge action.

## Decision — platform-specific exact load-symbol contract

- **Context:** The existing smoke build runs `nm -gU` on all hosts and only
  accepts `_load`. A mocked Red confirmed that ELF and Windows x64 need the
  GNU-compatible defined-symbol flags and unprefixed `load`; the existing
  search also accepts a similar `plugin._load` and an undefined `U _load`.
- **Decision:** Use Darwin's `nm -gU` and exact `_load` spelling on Mach-O;
  use `nm -g --defined-only` and exact `load` elsewhere. Validate the
  preceding nm symbol type as global text (`T`), normalize CRLF, and report
  `nm` invocation failures with their actual exit status and diagnostics.
- **Alternatives:** Keep a Darwin-only check and weaken the test to a substring;
  or accept either spelling on every platform. Both alternatives would let
  platform-inappropriate invocation or wrong/undefined symbols go unnoticed.
- **Rationale:** The platform ABI determines the external symbol spelling;
  a successful build smoke check must verify the exact defined text export
  that the matching loader expects.
- **Consequences:** The mocked test covers Darwin, ELF, and Windows x64
  formatting without claiming native Windows build/runtime validation.

## Verification evidence to date

- `PYTHONDONTWRITEBYTECODE=1 python3 tests/test_plugin_smoke_symbol_check.py`
  — meaningful Red: 6 tests ran, 5 failed against the current implementation
  for the portability, exact/defined-symbol, and nm-error-reporting behaviors.
- A preflight inspection command was initially issued with invalid
  `git branch` syntax (`git branch -vv --no-abbrev main`) and returned
  `fatal: a branch named 'main' already exists`; it did not create or change a
  ref. Corrected preflight using `git for-each-ref` verified the clean
  `main` tracking `origin/main` at the required base.
