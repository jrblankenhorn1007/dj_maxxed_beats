# Worker 01 decision record — PR pending

- **Run/task:** `ralph-main-review-20260925-021443` /
  `review-header-urls`
- **Agent:** `worker-01 / Windows header URL paths`
- **Runtime agent ID:** `null`
- **Branch:** `ralph/header-urls-worker-01-20260925-021443`
- **Worktree:** `/Users/jrblankenhorn/dj_maxxed_beats.worktrees/ralph-header-urls-worker-01-20260925-021443`
- **Base `origin/main`:**
  `f9e1bb3edafff1cc6d24c640a8e0ed38f5bf49fe`
- **Rebased onto `origin/main`:**
  `0736add11eae7b7f745d7b7bf9806c116d72eed6`
- **Implementation commit:**
  `694329fcf7022c9b0958d3a12f72fbaea5b8f2b0`
- **PR:** pending; the normal integration path is a worker-owned PR.

## Finding

The current implementation used `os.path.normpath` to normalize include
candidate paths that are appended directly to a `raw.githubusercontent.com`
URL. Under Windows semantics this produced backslash-separated URL paths.
The existing resolver intentionally swallows 404s for nonexistent candidate
locations, so the separator mismatch could silently leave transitive headers
unresolved and break the plugin build.

## Decision

Normalize URL-relative candidate paths with `posixpath.normpath` and add an
offline regression test that simulates Windows normalization and checks the
actual URL passed to a fake transport. Keep expected 404 handling limited to
missing candidate locations; do not add a fallback that masks invalid URLs or
other network errors.

- **Alternatives considered:** Keep host-path normalization; replace
  `os.sep` after normalization; or retry/backfill URLs using alternate
  separators.
- **Rationale:** URL path segments use forward slashes regardless of the
  host filesystem. `posixpath.normpath` expresses that invariant directly and
  does not widen the existing HTTP error policy.
- **Consequences:** The regression is covered without live network access.
  Native Windows 10 x64 and actual MacBook Neo execution remain unverified.

## Recovered test-harness issue

An initial simulation patched `os.path.normpath` in place on macOS. Because
`os.path` and the imported `posixpath` name referred to the same module, this
also changed the intended POSIX normalizer and made the first post-change
check fail for test-harness reasons. The test was corrected to substitute
`ntpath` only in the fetcher module's `os` binding, while mocking the actual
HTTP transport; the corrected test then reproduced the original bug and
passed with the fix. No production fallback was added.

## Integration

The PR number, URL, implementation SHA, and integration decision will be
recorded here after publication. The coordinator must authorize this exact
PR before the branch owner merges it.
