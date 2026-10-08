# Reviewer round 1 prompt

Perform an independent, read-only review of the exact PR diff in
`/Users/jrblankenhorn/dj_maxxed_beats.worktrees/ralph-copilot-guided-setup-20261007-2335`.
Compare base `68c7a9b709d7b5f9412e2358015f21af2bce8dcf` to head
`dd71106b1a2c14caa8897ec0f8ad5b7263d2e7af`; do not edit files or follow newer
branch state. Focus on high-confidence correctness/logic bugs, especially
whether the macOS/Linux/Windows setup-helper names/actions match packaged
launchers, whether missing Python/SDK errors reach the user-facing provider
callback, and whether the tests can pass incorrectly. Ignore style and
low-confidence speculation. Return findings with severity, exact file/line,
evidence and confidence; explicitly report no findings if none.
