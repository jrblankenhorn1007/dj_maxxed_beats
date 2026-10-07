# Worker assignments (summary)

The coordinator dispatched three parallel implementation workers on
2026-10-06 (about 23:17 UTC) from parent commit
`fa6decd2daaec8d5c4c22d947efaeef61804a743`, each in its own worktree and
child branch with disjoint owned paths. Runtime: VS Code Copilot task
subagents, agent type `general-purpose`, model `claude-opus-5.5`, reasoning
effort `max`.

| Worker | Child branch | Scope |
| --- | --- | --- |
| `worker-01` | `ralph/plugin-dsp-api-worker-01-20261006-2315` | DSP iteration-rate (`freq`) control with linear interpolation, `.kr`, `mul`/`add`, help, unit/NRT tests, agent guidance, sound-design notes. |
| `worker-02` | `ralph/plugin-build-install-worker-02-20261006-2315` | CMake build (universal macOS, Linux, Windows), user installer, install guide, installed-layout end-to-end test, cross-platform CI. |
| `worker-03` | `ralph/plugin-realtime-worker-03-20261006-2315` | Opt-in real-time `scsynth` verification test and local evidence. |

Each worker received the same shared-context block (repository layout,
SuperCollider 3.14.1 runtime paths, full-gate command, host constraints,
TDD/commit/evidence rules, and final-report format) followed by its own
assignment. This file is a **summary**, not the verbatim dispatch text; each
worker's progress log records the delivered scope and evidence.
