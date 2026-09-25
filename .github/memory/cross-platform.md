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
