# worker-03 provider-path decision record — PR pending

- **Branch:** `ralph/provider-path-worker-03-20260925-015713-e03cb755`
- **Base `origin/main`:**
  `f9e1bb3edafff1cc6d24c640a8e0ed38f5bf49fe`
- **Implementation commit:** pending
- **Worker:** `worker-03 / provider probe` (`worker-03`)
- **Runtime agent/session ID:** unavailable
- **PR:** pending coordinator review and branch publication

## Decisions

### Defer transport selection until a matching runtime probe is available

- **Context:** The project plan pins the first runtime target to official
  SuperCollider 3.14.1, but this worker environment has no `sclang` or
  `scsynth` executable. No Windows 10 x64 environment is available either.
  macOS `curl` and `security` tools and a source-level `NetAddr` observation
  cannot establish the language runtime's secure HTTPS, certificate
  validation, asynchronous completion, Keychain, or Credential Manager
  capabilities.
- **Alternatives:** Select direct sclang transport based on system tools or
  source inspection; add a helper before proving it is needed; or leave the
  transport gate open until matching runtime probes can run.
- **Rationale:** The last option follows the plan's "helper only if needed"
  boundary and avoids claiming unsupported platform/runtime evidence.
- **Consequences:** No provider transport architecture is selected and no
  production client/helper is introduced. A runtime-capable follow-up must
  test the same no-provider-key criteria on the required platforms. The
  smallest conditional fallback remains one internal helper shared by OpenAI
  and Anthropic if direct sclang capabilities prove insufficient.

## Recovered operational issues

- The first refresh command used `python`, which is not installed under that
  command name; rerunning with `python3` exposed a Python 3.9 f-string
  quoting syntax error. The lock/pull script was corrected, then both
  canonical and project `git pull --ff-only` operations completed successfully
  while holding the requested read-only-file advisory lock. No repository
  source was inspected or edited before the successful refresh.
- The first staged `git diff --cached --check` found trailing whitespace on a
  Markdown metadata line. The explicit Markdown hard break was removed; the
  same check then passed.

## Unresolved blocker

- No SuperCollider 3.14.1 runtime is present in the worker environment; no
  Windows 10 x64 target is present. Runtime HTTPS/TLS/async and credential
  store capabilities remain unverified. The exact environment evidence and
  distinction between source and runtime evidence are recorded in
  `docs/provider/path-feasibility.md`.

## Proposed shared decision-log entry

Propose adding an append-only project decision that defers direct-sclang versus
headless-helper selection until a matching SuperCollider 3.14.1 runtime probe
is available. Do not edit the shared `docs/decision_log.md` from this worker
branch; coordinator review owns any shared decision update.
