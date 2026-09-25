# Worker-01 decision record — PR pending

- **Run/task:** `headless-integration-tests-20260925-0246` /
  `implement-headless-test-pipeline`
- **Worker:** `worker-01 / headless test pipeline`
- **Runtime agent/session ID:** unavailable (`null`)
- **Branch:** `ralph/headless-integration-tests-worker-01-20260925-0246`
- **Base `origin/main`:** `0736add11eae7b7f745d7b7bf9806c116d72eed6`
- **Implementation commit:** pending commit
- **Pull request:** expected through the normal GitHub PR path; number and URL
  pending publication.

## Decision

- **Context:** The existing DSP unit and Python tests were separate
  invocations, and the real NRT integration must run rather than silently
  skip when `sclang` or `scsynth` is unavailable.
- **Alternatives:** Keep documenting separate commands; permit a runtime-
  missing skip; launch SCIDE as part of CI; or claim Windows coverage despite
  the current macOS-specific plugin smoke build.
- **Rationale:** A required CLI preflight plus one test-discovery command
  makes automated DSP/NRT coverage reproducible and gives an actionable
  missing-runtime failure. Pinning and hashing the official 3.14.1 DMG aligns
  the plugin test with its server API. The separate visual plan continues to
  govern GUI acceptance.
- **Consequences:** The pipeline runs the C++ DSP tests and all Python tests,
  including the ChaosOsc NRT render; CI is configured for macOS only. It
  launches no GUI, SCIDE, real-time server, or audio hardware and claims no
  Windows, MacBook Neo, or visual coverage. This is test infrastructure and
  does not advance product iteration 5.

## Recovered test-fixture issue

The first post-implementation contract-test run used `/bin/true` as a valid
executable fixture, but that path is unavailable on this macOS host. The test
now obtains Bash with `shutil.which("bash")`; the contract suite then passed.
No production behavior was implicated.

## Current integration state

Branch publication and PR creation are pending. No merge was attempted;
coordinator authorization is required before any worker-owned merge.
