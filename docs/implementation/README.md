# Per-branch implementation archive

This is the branch-centric index for implementation and code-review evidence.
The initial inventory was based on integrated `origin/main`
`7523a9a0b87ffc5304686e2e64509fc4a6941bb7`, plus terminal branches already
documented in the project Ralph records and this documentation-maintenance
branch. While this archive was being prepared, PR #24 advanced `origin/main`
to `ffbb4a36d642dd87b8fc3f45abd0b88399b5cea6`; its verified branch dossier is
included below. Add each future branch dossier on its working branch and
update this index when the branch is integrated.

## Record ownership and layout

Use the exact Git branch ref, lowercased with each `/` replaced by `-`, as
`<branch-slug>`. Every branch dossier has its own `README.md` and
`code-review/README.md`. New work also records task-specific prompts under
`prompts/`, dated agent handoffs under `agents/<stable-agent-id>/`, and a
`decisions/README.md` that links to the canonical decision records.

```text
docs/
  implementation/
    README.md
    <branch-slug>/
      README.md
      prompts/
        user-request.md
        worker-assignment.md
        reviewer-round-<n>.md
      agents/
        <stable-agent-id>/
          handoff.md
      decisions/
        README.md
      code-review/
        README.md
        round-01.md
        round-02.md
```

The archive is an index and evidence home, not a replacement for the shared
Ralph records. Keep current worker status and progress at
[`../ralph/`](../ralph/) and the aggregate dashboard at
[`../ralph-status.md`](../ralph-status.md). Keep append-only branch decisions
at [`../decisions/`](../decisions/). Link those canonical records from each
dossier instead of copying or moving their full histories.

## Prompt, handoff, and review records

- Save the actual task-specific user request and author/worker/reviewer
  assignments when available. Mark a paraphrase as a summary; do not present
  it as a verbatim prompt.
- Record dated handoffs, decisions, check results, and concise agent outputs
  under the stable agent ID. If a raw transcript is unavailable, say so rather
  than reconstructing one.
- Do not store credentials, tokens, secrets, private user data, hidden
  system/developer instructions, or private chain-of-thought. Preserve
  actionable findings and concise evidence-based rationale, not internal
  reasoning traces.
- Keep existing pre-archive history discoverable through its canonical links.
  Mark missing historical prompts, handoffs, or review reports
  `LEGACY_NOT_ARCHIVED`; this does not assert that no external review occurred.

For every PR-backed Ralph branch, use the independent read-only Ralph Code
Reviewer before merge, and add the Ralph Security Reviewer when the change
touches the shared policy's security-sensitive areas. Bind each report to the
exact full base and head SHAs and store the task-specific reviewer prompt,
structured findings, author action, and rationale in that branch's
`code-review/` folder. A required code and security report for the same
base/head pair is one review round. Allow at most two completed rounds: one
initial review and, if needed, one follow-up; after round two the author acts
on that report alone, with no third reviewer pass. Follow the
[project Ralph prompt](../RALPH_IMPLEMENTATION_PROMPT.md) and its canonical
Ralph PR Review skill for the complete gate.

Do not add a reviewer report to the audited PR branch while that PR is open:
doing so changes the reviewed head. Keep the report as sidecar evidence during
the gate, verify the SHAs again before merge, then archive the immutable report
in the dossier after integration. A no-PR integration has no reviewer pass;
record `NOT_APPLICABLE`. A historical PR without an archived report is
`LEGACY_NOT_ARCHIVED`, not a retroactive claim about whether it was reviewed.

## Integrated and documented branch inventory

The entries below cover the merged PR branches reported on the initial
`origin/main`, PR #24 which merged while this archive was being prepared, and
terminal attempts that already have project records. New work must create
its dossier before opening a PR. Open or otherwise unintegrated legacy
branches are not represented as merged history; their owners must follow the
current prompt before merging and add their dossier when integrated.

| Exact branch ref | Integrated or terminal state | PR / merge evidence | Dossier |
|---|---|---|---|
| `agents/ralph-loop-implementation-check-files` | Merged | PRs [#1](https://github.com/jrblankenhorn1007/dj_maxxed_beats/pull/1) and [#2](https://github.com/jrblankenhorn1007/dj_maxxed_beats/pull/2) | [Branch record](./agents-ralph-loop-implementation-check-files/README.md) |
| `ralph/iteration-3-5cd7160` | Merged | PR #3; merge `f3242bb5783237057c61b50b2dd4087bbf9d62d0` | [Branch record](./ralph-iteration-3-5cd7160/README.md) |
| `ralph/iteration-4-f3242bb` | Merged | PR #4; merge `b0b0f11f12538d174a6864bf362238361f4c9c68` | [Branch record](./ralph-iteration-4-f3242bb/README.md) |
| `ralph/music-skill-prompt-20260924-1945` | Merged | PR #5; merge `475ec183f262594a6f4ab3d08cf1ee9bec833553` | [Branch record](./ralph-music-skill-prompt-20260924-1945/README.md) |
| `ralph/iteration-5-vscode-nrt-475ec18` | Merged | PR #6; merge `b1c77ae9192491a86be5d42e86aebc10e3057a2d` | [Branch record](./ralph-iteration-5-vscode-nrt-475ec18/README.md) |
| `ralph/iteration-5-memory-followup-b1c77ae` | Merged | PR #7; merge `58b4f916603cc8e140c5e8c1bbca1290bb2dede6` | [Branch record](./ralph-iteration-5-memory-followup-b1c77ae/README.md) |
| `ralph/replace-beats-local-ralph-runner-worker-01-20260925-0105-refresh-58b4f91` | Merged | PR #8; merge `570bb69028f6ddf9bffa7391ba5d050852459941` | [Branch record](./ralph-replace-beats-local-ralph-runner-worker-01-20260925-0105-refresh-58b4f91/README.md) |
| `ralph/workflow-status-verify-20260925-0139` | Merged | PR #9; merge `f9e1bb3edafff1cc6d24c640a8e0ed38f5bf49fe` | [Branch record](./ralph-workflow-status-verify-20260925-0139/README.md) |
| `ralph/retire-beats-tdd-skill-worker-01-20260925-0108-refresh-570bb69` | Merged | PR #10; merge `0736add11eae7b7f745d7b7bf9806c116d72eed6` | [Branch record](./ralph-retire-beats-tdd-skill-worker-01-20260925-0108-refresh-570bb69/README.md) |
| `ralph/header-urls-worker-01-20260925-021443` | Merged | PR #13; merge `c448dae05f792ef868557e7d67a0a1becb7e6895` | [Branch record](./ralph-header-urls-worker-01-20260925-021443/README.md) |
| `ralph/headless-integration-tests-worker-01-20260925-0246` | Merged | PR #19; merge `160d062a4676cd9a46e25d5db2f0f90275887561` | [Branch record](./ralph-headless-integration-tests-worker-01-20260925-0246/README.md) |
| `ralph/readme-documentation-followup-20260925-0412` | Merged | PR #20; merge `9c8c1b679b765ace2b4ae1dac49c1ed827f43171` | [Branch record](./ralph-readme-documentation-followup-20260925-0412/README.md) |
| `ralph/readme-gh013-memory-followup-20260925-9c8c1b6` | Merged | PR #22; merge `1926bdab3c358088f359cf73f0d8025a66c7d0d0` | [Branch record](./ralph-readme-gh013-memory-followup-20260925-9c8c1b6/README.md) |
| `ralph/readme-status-reconcile-20260925-1926bdab` | Merged | PR #23; merge `7523a9a0b87ffc5304686e2e64509fc4a6941bb7` | [Branch record](./ralph-readme-status-reconcile-20260925-1926bdab/README.md) |
| `ralph/portable-plugin-load-symbol-check-worker-01-20260925-074130-refresh-7523a9a` | Merged | PR #24; base `7523a9a0b87ffc5304686e2e64509fc4a6941bb7`, head `ca94e4a4cddbe086ce13b10a17739bb6a5e53cce`, merge `ffbb4a36d642dd87b8fc3f45abd0b88399b5cea6` | [Branch record](./ralph-portable-plugin-load-symbol-check-worker-01-20260925-074130-refresh-7523a9a/README.md) |
| `ralph/replace-beats-local-ralph-runner-worker-01-20260925-0105` | Cancelled; superseded | No PR; see branch decision and worker progress | [Branch record](./ralph-replace-beats-local-ralph-runner-worker-01-20260925-0105/README.md) |
| `ralph/readme-docs-worker-01-20260925-0248` | Closed without merge; superseded | PR #17 closed; see branch decision | [Branch record](./ralph-readme-docs-worker-01-20260925-0248/README.md) |
| `ralph/iteration-3-b2f6a9e` | Preserved preflight-blocked attempt | No PR; implementation did not start | [Branch record](./ralph-iteration-3-b2f6a9e/README.md) |
| `ralph/implementation-records-coordinator-20260925-081730` | In progress | Parent PR pending | [Branch record](./ralph-implementation-records-coordinator-20260925-081730/README.md) |

## Reusable dossier template

Copy [`_template/`](./_template/README.md) to the exact branch slug. For a
historical dossier, populate only the information present in the repository
or verifiable PR metadata and label gaps explicitly.
