# Decisions — `ralph/windows-header-url-paths-worker-01-20260925-0250`

- **Run/task:** `ralph-cross-platform-review-luna-20260925-0250` /
  `windows-safe-plugin-header-url-paths`
- **Worker:** `worker-01 / Header URL portability`
- **Runtime agent ID:** `59ef35f9-cedd-4b76-9ae5-160362b7af8c`
- **Branch:** `ralph/windows-header-url-paths-worker-01-20260925-0250`
- **Branch slug:** `ralph-windows-header-url-paths-worker-01-20260925-0250`
- **Base `origin/main`:**
  `0736add11eae7b7f745d7b7bf9806c116d72eed6`
- **Implementation commit:** Pending creation; record its exact SHA before
  publishing the branch.
- **PR record:** [worker-01 pending PR](agents/worker-01/pr-pending.md)

## Append-only decisions

### DEC-001 — Normalize plugin-header URL paths with POSIX semantics

- **Date:** 2026-09-25
- **Context:** `plugin/fetch_sc_plugin_api.py` formed HTTP include candidates
  with the host `os.path.normpath` and then appended them directly to
  `BASE_URL`. A network-free regression that substitutes `ntpath` semantics
  reproduced backslashes in those candidate URLs.
- **Decision:** Use `posixpath.normpath` for URL-relative include candidates;
  continue using `os.path` for local cache paths. Keep a regression test that
  simulates the Windows normalizer and intercepts the HTTP boundary.
- **Alternatives:** Retain host path normalization and accept incorrect
  Windows URL paths; replace backslashes after host normalization; or stop
  normalizing include candidates. These alternatives either preserve the
  defect or keep URL handling coupled to filesystem semantics.
- **Rationale:** URL paths use `/` independent of the host OS. The test
  confirmed both the bad Windows-normalized requests before the fix and
  slash-only requests after it, without making a live network request.
- **Consequences:** Windows-style include resolution is covered by the
  focused test while filesystem cache handling remains host-native. The test
  does not replace native Windows 10 x64 or cross-platform CI verification.
- **Recovered operational issue:** An initial test-fixture patch changed
  `os.path.normpath` on the POSIX host, which also changed the shared
  `posixpath.normpath` module used by the fix. The fixture was corrected to
  replace only the fetcher's `os` adapter. The corrected test failed against
  the original implementation and passed against the fix; this issue is
  resolved.
