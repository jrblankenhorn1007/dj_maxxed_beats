# Worker-01 decision record — PR pending

- **Run/task:** `readme-refresh-20260925-0248` /
  `improve-root-readme`
- **Worker:** `worker-01 / root README and docs index`
- **Runtime agent ID:** `null` (not supplied)
- **Branch:** `ralph/readme-docs-worker-01-20260925-0248`
- **Base:** `origin/main` at
  `0736add11eae7b7f745d7b7bf9806c116d72eed6`
- **Implementation commit:** pending first commit
- **Pull request:** expected; not opened yet

## Decision — make the root README the product landing page

- **Context:** The root README only redirected readers to `docs/README.md`,
  while the latter contained the product overview. That split obscured
  current project state and made the repository root unhelpful to newcomers.
- **Alternatives:** Leave the product overview in `docs/README.md`, delete or
  rename that historical path, or move the overview to the root and retain
  `docs/README.md` as an index.
- **Rationale:** The assignment calls for a useful root landing page, and
  historical documentation already refers to `docs/README.md`. Keeping that
  path as a concise index improves discovery without repeating the overview.
- **Consequences:** `README.md` now explains the planned product, the
  prototype-only implementation state, developer commands and prerequisites,
  tested versus unverified platforms, and useful documentation links.
  `docs/README.md` is labeled as an index and links to the root README and
  root license. No product code or behavior is changed.

## Verification and integration

- `git diff --check` — PASS.
- Local Markdown links in the root README and docs index — PASS (19 checked,
  0 missing).
- TDD Red/Green/Refactor — not applicable; documentation-only.
- No merge has been attempted. The worker will wait for coordinator
  authorization before merging its PR.
