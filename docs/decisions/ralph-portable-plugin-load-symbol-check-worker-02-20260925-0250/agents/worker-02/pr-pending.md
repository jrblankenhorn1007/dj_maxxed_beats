# worker-02 PR pending — symbol-check portability review

- **Run/task:** `ralph-cross-platform-review-luna-20260925-0250` /
  `portable-plugin-load-symbol-check`
- **Worker:** `worker-02 / Plugin symbol portability`
- **Runtime session:** `copilotcli:/a17ae5a3-53fe-4381-a9fd-f590086cec29`
- **Branch:** `ralph/portable-plugin-load-symbol-check-worker-02-20260925-0250`
- **Base `origin/main`:**
  `0736add11eae7b7f745d7b7bf9806c116d72eed6`
- **Implementation commit:** pending.
- **PR number/URL:** pending; expected to use the repository's normal PR path
  after the branch is verified and published.

## Decision under investigation

- **Context:** The smoke script matched only a trailing `_load` symbol, while
  this project targets Windows 10 x64 as well as Apple Silicon macOS. The NRT
  test also asserted the exact `_load` success text. Independent Red evidence:
  `PYTHONDONTWRITEBYTECODE=1 python3
  tests/test_plugin_smoke_symbol_check.py` ran four tests; the Darwin `_load`
  fixture passed, but the ELF and Windows x64 unprefixed `load` fixtures
  failed with `expected exported symbol '_load' not found`. The test mocked
  header-fetch, compiler, and `nm`, so no network/compiler/platform claim is
  involved.
- **Alternatives:** Keep the Darwin-only match; match both exact `_load` and
  `load` names; or select separate matching logic by host platform.
- **Rationale:** Match both exact C-linkage spellings from the existing
  `nm -gU` output. This addresses the observed failure without coupling the
  test to a host name; near-match symbols remain invalid. Capture the `nm`
  output once and report tool failure separately from an absent loader symbol.
- **Consequences:** Update the NRT assertion for either verified symbol
  spelling. Mocked `nm` output verifies the smoke check logic only; no native
  ELF/Windows plugin build or runtime is claimed. Missing `nm` continues to
  produce the existing warning and skip behavior.
- **Recovered operational issues:** None at dispatch.
- **Unresolved blockers:** None at dispatch.
