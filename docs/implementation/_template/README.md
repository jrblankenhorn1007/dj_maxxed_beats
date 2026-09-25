# Branch dossier template

Copy this directory to
`docs/implementation/<lowercase-branch-ref-with-slashes-replaced-by-hyphens>/`
and replace the placeholders. Do not keep `_template` as a branch record.

Create `README.md`, `prompts/`, `agents/<stable-agent-id>/`,
`decisions/README.md`, and `code-review/README.md`. Link current status and
progress at `docs/ralph/<branch-slug>/agents/<agent-id>/` and decisions at
`docs/decisions/<branch-slug>/`; those remain the canonical histories.

Record exact, task-specific prompts and actual handoffs. Do not include hidden
system/developer instructions, secrets, or private chain-of-thought. Mark
unavailable history as unavailable; never reconstruct a verbatim prompt or
transcript from a summary.

For a PR, keep reviewer reports bound to exact full base/head SHAs. Do not
change the audited PR branch just to add a review report while it is open;
archive the sidecar report in `code-review/` after integration. The shared
policy allows at most two review rounds and requires an independent
Ralph Code Reviewer, plus a Ralph Security Reviewer for applicable security
diffs. No-PR integration uses `NOT_APPLICABLE`.
