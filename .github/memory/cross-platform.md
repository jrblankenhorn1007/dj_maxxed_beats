# Cross-platform paths memory

### Normalize protocol paths using protocol semantics
- **Rule:** Treat URL path fragments as protocol paths, not local filesystem
  paths. Normalize them with URL/POSIX separators on every host, converting
  to native filesystem paths only at the actual filesystem boundary.
- **Why:** PR #13's Windows-path regression simulated `ntpath` and reproduced
  backslash-separated `raw.githubusercontent.com` URLs. The upstream returned
  404 for those candidates, and the resolver treated them as expected missing
  includes. Using `posixpath.normpath` preserved forward slashes and resolved
  the transitive header; the offline test asserts the exact URL and forbids
  backslashes.
- **Scope:** URL-relative paths, including plugin API header fetching.

### Keep C++ array bounds constant without lambda capture
- **Rule:** Declare constants used as array bounds inside lambdas as
  `static constexpr` (or at namespace scope) so MSVC treats them as constant
  expressions.
- **Why:** A local `constexpr int` array bound inside a `[&]` lambda compiled
  with Clang but failed MSVC with C2131 in Plugin Builds run `37554551784`
  (PR #33); `static constexpr` fixed it in PR #34.

### Parse Windows Credential Manager output by target records
- **Rule:** Detect a stored credential from an actual `Target:` record and
  compare its parsed value with the requested target. Treat the
  `Currently stored credentials for ...` line as a heading, not a credential;
  support legacy target syntax only as an explicit record format.
- **Why:** Windows CI run `37578448992` showed `cmdkey /list` output whose
  heading echoed the requested target while the stored entry appeared in a
  separate `Target:` record. A suffix-only assertion rejected the real entry.
  The parser tests now cover current and legacy records plus an empty-listing
  heading, and the Windows Credential Manager suite passed in PR run
  `37653854390`. See
  [the parser tests](../../tests/test_mb_providers_wincred.py) and
  [iteration 8 evidence](../../docs/RALPH_PROGRESS.md).
- **Scope:** Windows Credential Manager listing and its tests.

### Launch Windows test helpers with argument arrays
- **Rule:** When an sclang test must launch a Windows helper with filesystem
  paths, use `Pipe.argv` and pass each path as its own argument instead of
  nesting path-bearing commands in `cmd.exe /c` text.
- **Why:** The old `cmd.exe /c move` render fixture failed to plant its
  sentinel symlink in Windows CI run `37578448992`, which also failed scenario
  completion. A PowerShell helper launched with `Pipe.argv` passed the
  malicious-log test and the Windows Assistant Tests in run `37653854390`.
  See [the render fixture](../../tests/test_mb_workflow_render.py) and
  [its helper](../../tests/mb_workflow/plant_render_log.ps1).
- **Scope:** Windows subprocess fixtures launched from sclang.
