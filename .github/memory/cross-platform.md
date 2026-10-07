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
