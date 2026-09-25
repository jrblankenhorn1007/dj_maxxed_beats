# Worker-02 PR pending — portable plugin load symbols

- **Run/task:** `ralph-main-review-20260925-021443` /
  `review-symbol-check`
- **Worker/runtime:** `worker-02 / portable plugin load symbols` /
  `copilotcli:/a17ae5a3-53fe-4381-a9fd-f590086cec29`
- **Iteration:** 1
- **Exact branch:** `ralph/plugin-symbols-worker-02-20260925-021443`
- **Starting base:** `origin/main`
  `f9e1bb3edafff1cc6d24c640a8e0ed38f5bf49fe`
- **Rebased base:** `origin/main`
  `0736add11eae7b7f745d7b7bf9806c116d72eed6`
- **Implementation commit:**
  `00c24f247b4bc8313217b237352e9004bae5aea0`
- **PR:** pending normal publication and creation
- **Current integration state:** `IN_PROGRESS`; do not merge until the
  coordinator authorizes this exact PR.

## Decision — use platform-correct load symbol names and `nm` modes

- **Context:** The plugin smoke build used Darwin's `nm -gU` and required
  `_load` unconditionally. On ELF and Windows x64, the C export is named
  `load`; a valid plugin was rejected. The old pipeline also obscured the
  distinction between an absent symbol and an `nm` execution failure.
- **Alternatives:** Keep the Darwin-only test; accept either `load` spelling
  on every platform; skip the check when `nm` fails; or select the symbol
  spelling and defined-symbol filter for the host platform.
- **Decision:** Keep `nm -gU` and `_load` on Darwin. On other supported
  targets use `nm -g --defined-only` and the exact `T load` entry. Reject
  missing, undefined, or similarly named symbols. When `nm` exists, surface
  its failure status and diagnostic; only warn/skip when it is unavailable.
- **Rationale:** A platform-specific exact symbol check preserves macOS
  behavior while accepting the C symbol name reported on ELF/Windows and
  keeping undefined imports or similarly named symbols from satisfying the
  smoke check.
- **Consequences:** Mocked platform tests can validate names, flags, and
  failure handling without downloading headers or requiring a Windows
  toolchain. A real Windows DLL/export and SuperCollider load/runtime check
  remain separate platform verification.

## Verification evidence and resolved issue

See the worker leaf
[`progress.md`](../../../../ralph/ralph-plugin-symbols-worker-02-20260925-021443/agents/worker-02/progress.md)
for exact Red, Green, and refactor commands/results. The first Green test
attempt exposed only an assertion wording mismatch (`nm` was quoted in the
new diagnostic); the test assertion was corrected and all seven targeted
tests passed.

## Merge decision

No merge action has been taken. The branch owner will merge only after the
coordinator authorizes this exact PR; publication or an open PR is not
completion.
