# Worker decision index — portable plugin load symbols

- **Run/task:** `ralph-main-review-20260925-021443` /
  `review-symbol-check`
- **Worker:** `worker-02 / portable plugin load symbols`
- **Exact branch:** `ralph/plugin-symbols-worker-02-20260925-021443`
- **Branch slug:** `ralph-plugin-symbols-worker-02-20260925-021443`
- **Starting `origin/main`:**
  `f9e1bb3edafff1cc6d24c640a8e0ed38f5bf49fe`
- **Rebased `origin/main`:**
  `0736add11eae7b7f745d7b7bf9806c116d72eed6`
- **Implementation commit:**
  `00c24f247b4bc8313217b237352e9004bae5aea0`
- **PR record:** [worker-02 PR pending](./agents/worker-02/pr-pending.md)

## Decision summary

- Verify the platform's exact defined C `load` symbol: `_load` with Darwin
  `nm -gU`, and unprefixed `load` with `nm -g --defined-only` elsewhere.
- Treat a nonzero `nm` invocation as an inspection failure, not as evidence
  that the export is merely absent.
- Preserve the existing warning-and-skip behavior only when `nm` is not
  installed.
