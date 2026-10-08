# Coordinator assignment

The active SCIDE process had the configured Python 3.14.8, Copilot SDK
1.0.16, and CLI, but model refresh reported unauthenticated. Reproduce the
failure in the same app environment, identify the root cause, add a
test-first regression, and preserve the existing session isolation/tool
denial. Do not claim completion until the installed active window is verified.

The bridge passed the request's temporary directory as
`CopilotClient.base_directory`, which redirected `COPILOT_HOME` away from the
user's saved login. PR #53 omitted that override and merged at
`3515844e4db4b7a6a58a2d1ed1a49b9e518cc8a5`.
