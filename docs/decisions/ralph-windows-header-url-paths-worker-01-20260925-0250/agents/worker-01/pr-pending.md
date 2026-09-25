# Worker-01 PR record — pending assignment

- **Run/task:** `ralph-cross-platform-review-luna-20260925-0250` /
  `windows-safe-plugin-header-url-paths`
- **Worker:** `worker-01 / Header URL portability`
- **Runtime agent ID:** `59ef35f9-cedd-4b76-9ae5-160362b7af8c`
- **Branch:** `ralph/windows-header-url-paths-worker-01-20260925-0250`
- **Worktree:** `/Users/jrblankenhorn/dj_maxxed_beats.worktrees/ralph-windows-header-url-paths-worker-01-20260925-0250`
- **Base `origin/main`:**
  `0736add11eae7b7f745d7b7bf9806c116d72eed6`
- **Implementation commit:**
  `bc7ca3bf8065d142043848c0777c09583bbf5f71`
- **Pull request:** Pending; no number or URL assigned yet.
- **Merge actor:** `worker-01` only after coordinator authorization of this
  exact PR.

## Decision record

- **Context:** `plugin/fetch_sc_plugin_api.py` built include candidates with
  host `os.path.normpath` and appended those paths directly to the HTTP base
  URL. The network-free test using `ntpath` semantics confirmed generated
  candidates contained backslashes on Windows-style path normalization.
- **Decision:** Use `posixpath.normpath` for URL-relative candidates and keep
  `os.path` for local cache paths.
- **Alternatives:** Retain host `os.path.normpath` and accept incorrect
  Windows URLs; replace backslashes after host normalization; or skip path
  normalization. The first retains the defect, the second remains coupled to
  filesystem behavior, and the third can preserve unnecessary `.`/`..`
  components in URL paths.
- **Rationale:** HTTP URL paths use POSIX `/` separators on every host. The
  focused test confirmed the old implementation emitted Windows
  backslashes and that the fix emits slash-separated candidates without
  network access.
- **Consequences:** Header include discovery now keeps URL path semantics
  independent of the machine's filesystem while disk cache paths remain
  platform-native. Native Windows 10 x64 and cross-platform CI remain
  unverified.
- **Recovered operational issue:** The first Green attempt failed because
  patching `os.path.normpath` on the POSIX host also changed the shared
  `posixpath.normpath` module used by the fix. Replacing only the script's
  `os` adapter fixed the test simulation. The corrected test was Red against
  the original implementation and Green against the fix; no blocker remains.

## Verification

- **Red:** `PYTHONDONTWRITEBYTECODE=1 python3 tests/test_fetch_sc_plugin_api.py FetchScPluginApiTests.test_generated_http_candidate_paths_use_posix_separators_on_windows`
  failed against the original implementation, showing backslash-separated
  candidate URLs.
- **Green:** The same command passed after the minimal fix.
- **Final focused module:** `PYTHONDONTWRITEBYTECODE=1 python3 tests/test_fetch_sc_plugin_api.py`
  passed all 7 tests on macOS 26.5.2 arm64, Python 3.9.6.
- **Diff check:** `git diff --check` passed.
- **Network/platform gaps:** Tests used a fake `urlopen`; no live network was
  used. Native Windows 10 x64 execution and cross-platform CI remain
  unverified.

## Integration protocol

This record is pending PR assignment. Before merge, update it to the assigned
PR number and URL, record the PR/check state, and update the branch decision
index and worker leaf status. Do not merge until the coordinator authorizes
this exact PR; the branch-owning worker then merges only through the
repository's normal permitted process.
