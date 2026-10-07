# Provider layer design (worker-01)

Scope: `extension/Classes/Providers/**`, `extension/Data/**`, and
`tests/test_mb_providers_*.py` + `tests/mb_providers/`. Implements the
provider section of [CONTRACT.md](CONTRACT.md); extensions to that interface
are listed under [Contract extensions](#contract-extensions).

## Phase-0 transport decision: direct sclang + OS `curl` (no helper)

**Decision.** Provider HTTPS runs from sclang by launching the operating
system's `curl` asynchronously (`unixCmd` with an exit action). No bundled
headless helper is needed. Credentials use each OS store's own CLI
(`security`, `secret-tool`, PowerShell + `advapi32` Cred* APIs).
This supersedes the "defer" proposal in
[path-feasibility.md](../provider/path-feasibility.md), which had no runtime.

**Evidence (SuperCollider 3.14.1, macOS 26 arm64, curl 8.7.1/SecureTransport,
2026-10-06).**

| Requirement | Result | How it was verified |
| --- | --- | --- |
| TLS certificate validation | Enforced; never `-k` | Live non-provider probe from sclang via `MBHttp`: `https://example.com` → 200; `self-signed.badssl.com`, `expired.badssl.com`, `wrong.host.badssl.com` → `\network` "TLS/certificate verification failed (curl 60)". Offline regression: `test_tls_certificate_validation_is_enforced` (self-signed loopback server; server receives no request). |
| Non-blocking | `complete` returns in < 0.2 s; AppClock keeps ticking (> 15 ticks during a 1.5 s request) | `test_requests_are_non_blocking_and_time_out`; live probe issued 4 HTTPS requests in 0.043 s. Only µs–ms local work (mkdir/mkfifo via `systemCmd`, writing the request body) runs synchronously. |
| Timeout | curl `--max-time` → `\network` "timed out"; AppClock watchdog at timeout + 10 s as backstop | same test (1.5 s timeout vs 4 s server delay) |
| Cancellation | `handle.cancel` → `pkill -P <sh>` + `kill <sh>`, `\cancelled` delivered once, no late success, curl gone | `test_cancel_stops_the_request_promptly` |
| Keys absent from argv/env | `ps -axww` and `ps -axwwE` snapshots taken while the server holds the request contain no key | `test_openai_request_and_response_mapping` |
| macOS Keychain round trip | store/has/validate/use/remove via `security`, temporary keychain file only | `test_store_use_validate_and_remove_key_in_temporary_keychain` (verifies the user keychain search list is unchanged) |
| Windows Credential Manager round trip | store/replace/has/validate/use (both auth headers)/remove via the PowerShell helper, unique test-only targets `MaxxedBeatsTest-<random>:<id>`, always deleted afterwards (`cmdkey /delete`) | `test_mb_providers_wincred.py` (Windows runner) |

**Windows (Windows 10 1803+ / 11 x64; verified on the hosted `windows-latest`
runner by the Assistant Tests workflow).** `%SystemRoot%\System32\curl.exe`
(Schannel, validates against the Windows certificate store; never `-k`) gets
the same non-secret arguments as on POSIX. No shell parses anything:

1. `MBHttp` writes `<run dir>/curl-spec.json` (`curl`, `args`, `headerPrefix`;
   no key) and `MBProcess` starts the bundled helper
   `Data/windows/MaxxedBeatsCredential.ps1` with `Pipe.argv` (Windows
   PowerShell 5.1, `-NoProfile -NonInteractive -ExecutionPolicy Bypass`), so
   the helper's stdin is a pipe from sclang. Its argv names only the action,
   the run directory, and the credential target (`MaxxedBeats:<id>`).
2. The helper reads the key from Credential Manager (`CredReadW`; or, for
   `MBCredentialStore.fake`, the single line sclang wrote to its stdin),
   validates it, starts curl.exe with `RedirectStandardInput`, and writes
   only `header = "<prefix><key>"` to curl's stdin (`-K -`). The key never
   enters argv, environment variables, files, or output.
3. The helper prints nothing; it writes `stderr.txt` (a message without
   secrets) and, last, `exit-code.txt`. sclang polls for that file every
   50 ms on AppClock, so requests stay asynchronous. The `Pipe` is closed a
   few seconds later (its close waits for the process).
4. Cancel and timeout: `taskkill /F /T /PID <helper>` stops the helper and
   curl; curl `--max-time` plus the AppClock watchdog bound every request.

Evidence on the Windows runner: the whole `test_mb_providers_http.py` suite
(request mapping, model lists, error mapping, timeout, cancellation, TLS
rejection of a self-signed loopback server, non-blocking) and the
Credential Manager round trip below. During requests the tests read every
visible process's command line and environment block (PEB on Windows,
`ps -E`/`/proc` elsewhere) and assert the key is absent.

**Alternatives rejected.** A bundled helper (extra binary to sign/ship per
platform, IPC surface) is unjustified since the direct path meets every
requirement on macOS. sclang has no native HTTP/TLS client (`NetAddr` is
raw TCP/UDP only). `Pipe`-based reads block the interpreter; not used for HTTP.

## Secret handling

- Keys never enter process arguments, environment variables, files, logs, the
  post window, settings, or error text. They are never returned to sclang
  after `storeKey`.
- Request pipeline (POSIX, one `/bin/sh -c` script per request):
  `key=$(<store read>) || exit 120` → validated charset →
  `printf 'header = "%s%s"\n' <prefix> "$key" | curl -q -K - …`. `key` is an
  unexported shell variable; `printf` is a builtin (no exec/argv). `-q`
  ignores `~/.curlrc` so user config cannot enable tracing.
- Store reads: macOS `security find-generic-password -s MaxxedBeats -a <id> -w`;
  Linux `secret-tool lookup service MaxxedBeats account <id>`; Windows
  `MaxxedBeatsCredential.ps1` (`MaxxedBeats:<id>` generic credential, UTF-8
  blob, `CRED_PERSIST_LOCAL_MACHINE`; `MBWindowsCredentialStore.new(prefix)`
  changes the target prefix, used only by tests).
- Windows writes: `storeKey` starts the helper with `Pipe.argv` and writes the
  key line to its stdin (`CredWriteW`); `has`/`remove` use `CredReadW`/
  `CredDeleteW` (an absent key is not a removal error).
- Writes from sclang (`storeKey`) and the in-memory `MBCredentialStore.fake`
  pass the key through a private **FIFO** (mode 600 in a 700 directory; the
  node is unlinked as soon as both ends are open; data never rests on disk):
  `security -i < fifo` (command line containing `-w <key>` read from stdin),
  `secret-tool store … < fifo`. A guard process opens the FIFO after 3 s if the
  child died first, so sclang never blocks indefinitely.
- Keys are validated (8–512 chars, `[A-Za-z0-9_.-]`, alphanumeric first) so
  they cannot inject into backend command streams or curl config lines.
- Error detail is passed through `MBRedact.string` (key shapes `sk-…`,
  `Bearer …`, `x-api-key: …`, `Authorization: …`, known secrets) and truncated.
  Provider error bodies are reduced to their `message`; headers are never
  included. curl's stderr never contains request headers (no `-v`).
- Only `https://` base URLs are accepted; plain `http://` only for loopback
  test servers. curl runs with `--proto =https`, no redirects followed.
- Per-request scratch directories (`<settings>/run/req-*`, mode 700; on
  Windows inside the per-user `%LOCALAPPDATA%`) hold the request body, response
  headers/body, curl stderr, and on Windows `curl-spec.json` and
  `exit-code.txt` — never a key — and are removed when the request finishes
  (Windows retries while a killed child still holds the folder); leftovers
  older than 2 h are purged.

## Providers

| | OpenAI (`\openai`) | Anthropic (`\anthropic`) |
| --- | --- | --- |
| Generate | `POST /v1/responses` `{model, instructions, input:[{role,content}], max_output_tokens, temperature?, store:false}` | `POST /v1/messages` `{model, system?, messages, max_tokens, temperature?}`, `anthropic-version: 2023-06-01` |
| Auth header | `Authorization: Bearer` | `x-api-key` |
| Text | concatenated `output[type=message].content[type=output_text].text` (reasoning items ignored; refusal text returned with `stopReason: "refusal"`) | concatenated `content[type=text].text` (thinking blocks ignored) |
| Usage | `input_tokens`, `input_tokens_details.cached_tokens` / `cache_write_tokens`, `output_tokens` | `inputTokens = input + cache_read + cache_creation`; cached = `cache_read_input_tokens`; write = `cache_creation_input_tokens` (+ `cacheWrite1hInputTokens` when reported) |
| requestId | `x-request-id` header | `request-id` header |
| Models | `GET /v1/models`; non-text models labeled `usable: false` with a note (embedding, tts, whisper, image, realtime, search, …) | `GET /v1/models?limit=1000`, follows `has_more`/`after_id` (≤ 20 pages) |

Errors (no retries, no fallback): curl/transport → `\network` (TLS, DNS,
connect, timeout) or `\config` (curl missing / bad base URL); missing or
malformed stored key → `\auth` with no network call; HTTP 401/403 → `\auth`;
429 → `\rateLimit` (+ `retry-after`); model not found (OpenAI
`model_not_found`, Anthropic 404 `not_found_error` "model…") →
`\unavailableModel`; 400/409/413/422 → `\validation`; 408/5xx/529 → `\server`;
malformed/unexpected 2xx JSON or no text → `\parse`; output budget exhausted
before any text → `\validation`. Request shape is validated before sending.

`MBMockProvider` (`\mock`, "Mock DJ (offline)"): models `mock-composer-1`
(usable) and `mock-legacy-0` (unusable); `complete` returns a deterministic
JSON placeholder `{mock, digest, plan, summary, edits: []}` derived only from
the request. Adjust with `responder`, `enqueue(text | MBError | function)`,
`latency`, `models`, `listModelsError`. Swap the default responder once the
workflow layer fixes the composition response format.

## GitHub Copilot subscription provider

`MBCopilotProvider` (`\copilot`) uses the official GitHub Copilot SDK and CLI,
not the GitHub Models API or an OpenAI-compatible endpoint. The CLI owns
GitHub sign-in and subscription authentication; MaxxedBeats does not request
or store a Copilot API key or reuse VS Code credentials. Its GUI sign-in
control appears as a provider row alongside the OpenAI and Anthropic key rows.

The optional bridge is `extension/Data/copilot/bridge.py`, with its pinned
`github-copilot-sdk` dependency in `requirements.txt`. The official Copilot
CLI is located from the provider's saved runtime configuration, the native
per-user CLI install locations, or `PATH`; this avoids depending on the
environment inherited by SCIDE. The setup helper
`extension/Data/copilot/setup_copilot.py` creates a private Python 3.11+
virtual environment, installs the pinned SDK, and saves its Python and CLI
paths to `<settings>/copilot-runtime.json`. The settings contain no tokens.
macOS/Linux launch scripts install the official CLI per user and guide the
user through obtaining Python 3.11+; the Windows package has a one-click
launcher which optionally installs Python and the official CLI using WinGet.
The bridge refreshes saved paths for an already-open SCIDE session, runs from
an isolated temporary directory with tools and discovery disabled, exposes
only sign-in, auth-status, model-list, and completion actions, and returns
structured results to sclang. Model availability comes from the runtime, not
a hard-coded catalog. Unit tests use fakes and do not claim live login or
completion.

## Model catalog

`MBModelCatalog(registry, settingsDir, clock)`; `.default`.
Cache: `<settings>/model-catalog.json`; selections:
`<settings>/providers.json` (`selectedModels`), where `<settings>` =
`Platform.userConfigDir/MaxxedBeats`. A list is stale when the last refresh
failed (cached list kept, `lastError(id)` set) or it is older than
`maxAgeSeconds` (24 h). `selectModel` only accepts a usable model from the
current list. `checkSelection(id)` returns `nil` or
`MBError(\unavailableModel)`; the selection is never changed automatically.

## Usage, cost, credits

Rate table: [`extension/Data/provider-rates.json`](../../extension/Data/provider-rates.json),
schema 1, version `2026-10-06.1`, retrieved 2026-10-06 from
<https://developers.openai.com/api/docs/pricing>,
<https://developers.openai.com/api/docs/guides/prompt-caching>,
<https://platform.claude.com/docs/en/about-claude/pricing>, and the Claude models
overview / deprecations pages (for API IDs). Standard tier, USD per 1M tokens.
Only models whose price **and** API ID were on those pages are listed;
everything else is unpriced (`nil`). OpenAI long-context rates apply above
272K input tokens; Claude Sonnet 4.5 / Haiku 4.5 above 200K are left unpriced.
Snapshot suffixes (`-YYYY-MM-DD`, `-YYYYMMDD`) and listed aliases map to the
base entry. Rates are `\stale` after `staleAfterDays` (45) or an entry's
`validUntil` (GPT-5.6 Sol promo, 2026-11-21); stale rates still produce an
estimate, labeled stale. Regional/data-residency uplifts, batch, and
priority/fast tiers are not modeled.

`MBUsageMeter(rateTable, historyPath, today)`; `.default`. Credits = USD ×
`creditsPerUSD` (100). `sessionTotals` sums tokens and priced USD and reports
`pricedRequests`, `unpricedRequests`, `complete`, and the worst `rateStatus`.
History: `<settings>/usage-history.json` (last 5000 records, no prompts or
secrets), `.history`, `.clearHistory`, `.resetSession`.

## Contract extensions

- Response adds `stopReason`, `responseId`; usage adds
  `cacheWriteInputTokens` (and `cacheWrite1hInputTokens` for Claude when
  reported). `inputTokens` is always the total input.
- Meter record adds `cacheWriteInputTokens`, `rateReason`, `requestId`, `time`.
  Nil fields are absent from Events (sclang drops nil values).
- `MBModelCatalog`: `.usableModels`, `.lastError`, `.checkSelection`,
  `.maxAgeSeconds`; `.selectModel` returns `nil` or an `MBError`.
- `MBCredentialStore.validateKey(id, onSuccess, onFailure, provider)`:
  optional provider; success passes the model list.
- Constructors for tests: `MBOpenAIProvider/MBAnthropicProvider.new(store,
  baseUrl, timeout)`, `MBProviderRegistry.new(store, providers)`,
  `MBKeychainCredentialStore.new(keychainPath)`,
  `MBWindowsCredentialStore.new(targetPrefix)`.
- On Windows the backend hooks (`keyPrelude`, `hasCommand`, `storeCommand`,
  `removeCommand`) answer argv Arrays for the helper instead of shell text.
- All handles are `MBRequestHandle` (`.cancel`, `.isDone`, `.isCancelled`).

## Implementation notes

- `MBJSON` is a strict RFC 8259 parser/encoder (sclang's `parseJSON` is YAML
  and turns every scalar into a String). Integers beyond 9 digits parse as
  Float (32-bit `Integer`).
- sclang 3.14 pitfall: an exception thrown while evaluating a call argument
  (e.g. `dict.put(key, this.parse)`) corrupts later calls inside Routines;
  evaluate into a variable first.

## Proposed decision-log entries

1. 2026-10-06 — Provider transport: direct sclang + OS curl, no helper
   (context/evidence above). Windows verified 2026-10-07 (DEC-041).
2. 2026-10-06 — Secrets flow store → shell variable → curl stdin; FIFO for
   writes; keys never returned to sclang.
3. 2026-10-06 — OpenAI uses the Responses API with `store: false`.
4. 2026-10-06 — Rate table lists only rates verified that day; unknown is nil.

## Gaps

- Windows backend and transport are verified on the hosted Windows runner
  (Windows Server, Windows PowerShell 5.1); a physical Windows 10/11 PC is
  the friend's manual check. Linux `secret-tool` backend is tested only for
  command generation.
- Windows: each helper start costs a PowerShell launch (about 0.5–1 s, plus
  about 1 s to compile the Credential Manager P/Invoke types); acceptable
  next to provider latency.
- No streaming; no automatic re-pricing for regional endpoints or priority tiers.
- The mock's response format is a placeholder pending worker-02's format.
