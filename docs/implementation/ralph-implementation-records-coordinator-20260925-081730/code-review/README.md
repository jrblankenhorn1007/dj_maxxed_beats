# Code review archive — coordinator documentation archive

- **PR state:** `PENDING`; the parent PR has not been opened.
- **Review state:** `PENDING`; no reviewer has been dispatched for this
  branch yet.
- **Required reviewer:** independent read-only Ralph Code Reviewer.
- **Security reviewer:** not indicated for this documentation-only diff.
- **Review limit:** at most two completed rounds, with no third pass.

When the PR exists, record its exact full base/head SHAs and reviewer prompt.
The task-specific first-round prompt is in
[`prompts/reviewer-round-01.md`](../prompts/reviewer-round-01.md); the
coordinator supplies the verified PR base/head SHAs with the dispatch.
Keep the report as sidecar evidence while the PR is open; do not change the
audited branch to add the report. After integration, archive the structured
report and the author's disposition in `round-01.md` (and `round-02.md` only
if a follow-up occurs). Do not claim a review result before it is produced.
