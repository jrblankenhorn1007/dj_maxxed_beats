# Provider path feasibility: SuperCollider 3.14.1

**Phase:** 0 — product boundary
**Result:** **BLOCKED for runtime capability selection.** This checkout
contains no runnable SuperCollider language runtime, so secure asynchronous
HTTPS and credential-store behavior from `sclang` could not be verified. This
report records the exact environment gap; it does not turn host-tool or source
observations into runtime claims.

## Target and scope

The project plan names official SuperCollider 3.14.1, release commit
`426edf6d8742e1cc3bd85b51ca0c4e595d37a903`, as the initial runtime/API target.
The probe scope is whether that supported language runtime can supply:

- asynchronous HTTPS with normal certificate validation, suitable for
  non-billable OpenAI and Anthropic requests; and
- safe access to macOS Keychain and Windows Credential Manager without
  exposing provider keys to project files, logs, or process arguments.

No provider key was read or created, no provider API was called, and no
billable request was made.

## Evidence collected on this worker

| Observation | Result | What it does—and does not—establish |
| --- | --- | --- |
| `uname -srm` | `Darwin 25.5.0 arm64` | This worker host is Darwin/arm64. It does not identify a MacBook Neo. |
| `sw_vers -productVersion` / `sw_vers -buildVersion` | `26.5.2` / `25F84` | Host OS/build only; not SuperCollider runtime evidence. |
| `command -v sclang scsynth` | Both unavailable | There is no `sclang` or `scsynth` executable on this worker's `PATH`. |
| Documented ignored runtime path under the integration checkout | `sclang` and `scsynth` not executable/present | The earlier iteration's runtime path is not available from this worker environment. |
| Common installed app/Homebrew paths checked | `sclang` unavailable | No matching local 3.14.1 app/runtime was found at the checked paths. |
| `curl --version` | `curl 8.7.1`, SecureTransport backend | An OS-level HTTPS client exists; this does not show that `sclang` can invoke it safely or asynchronously. |
| `/usr/bin/security -h` | macOS `security` CLI is present | This does not prove `sclang` can use Keychain APIs or perform a safe credential round-trip. No Keychain entry was touched. |
| `command -v powershell pwsh` | Both unavailable | No Windows PowerShell or Windows Credential Manager target is available here. |
| `supercollider/` in the fresh worktree | Not present | The project’s optional upstream source-review checkout is not available locally in this worktree. |

The exact release-pinned `NetAddr` class source is available at
[the official 3.14.1 source commit](https://github.com/supercollider/supercollider/blob/426edf6d8742e1cc3bd85b51ca0c4e595d37a903/SCClassLibrary/Common/Control/NetAddr.sc).
That source defines `tryConnectTCP` using a language `fork` and the
`_NetAddr_Connect` primitive. This is a **source observation about that class**
and its TCP connection path only. It does not demonstrate TLS, HTTP,
certificate validation, credential-store access, or actual behavior in a
running 3.14.1 process; it also does not rule out other facilities.

## Capability matrix

| Capability | Status | Evidence |
| --- | --- | --- |
| Direct `sclang` HTTPS request | **NOT VERIFIED** | No 3.14.1 `sclang` runtime was available to execute a request. |
| HTTPS certificate validation | **NOT VERIFIED** | `curl`’s TLS backend is an OS-tool observation, not an `sclang` result. |
| Asynchronous HTTPS completion while language work continues | **NOT VERIFIED** | No language process was available to test callbacks, scheduling, or blocking. |
| `sclang` access to macOS Keychain | **NOT VERIFIED** | The `security` CLI exists, but it was not invoked through `sclang`; no store read/write was attempted. |
| `sclang` access to Windows Credential Manager | **NOT TESTED** | This host is macOS and has no Windows runtime or Credential Manager. |
| OpenAI or Anthropic provider request | **NOT RUN** | No provider key, endpoint call, or billing was used. |

The absence of `sclang` is an environment limitation, not evidence that
SuperCollider 3.14.1 lacks a capability. Conversely, the presence of `curl`,
`security`, or a source-level TCP API is not evidence that the language-side
provider path is secure, asynchronous, or cross-platform.

## Architecture disposition

No provider transport architecture is selected by this iteration. The
smallest justified action with the evidence available is to add **no
production HTTP client and no helper** yet, and keep the phase-0 decision
open. This follows the plan’s requirement to add a helper only if a direct
language-side path is shown insufficient; that condition has not been tested.

Once a matching runtime is available, test one common transport path for both
providers. If and only if direct `sclang` HTTPS or credential-store access
fails the required checks, the plan-aligned fallback is one internal,
headless helper shared by the OpenAI and Anthropic adapters—not one helper per
provider—with a restricted local IPC boundary and platform-native credential
handling. That fallback is conditional, not a finding of this probe; no
helper code or provider adapter is proposed here.

## Reproduction and next evidence needed

The environment inventory for this report used:

```sh
uname -srm
sw_vers -productVersion
sw_vers -buildVersion
command -v sclang
command -v scsynth
command -v curl
command -v security
command -v powershell
command -v pwsh
```

The runtime checks cannot be reproduced until the official 3.14.1 runtime is
provided. A follow-up probe should first confirm the executable/runtime
version, then use a non-provider HTTPS GET with no authorization headers to
observe successful certificate validation, completion callbacks, timeout
behavior, and language scheduling. Credential-store round trips should use
only a synthetic non-provider sentinel, report pass/fail without printing its
value, and remove it afterward. Run the corresponding Windows test on Windows
10 x64; macOS CLI availability must not be used as Windows evidence. Do not
call either provider or infer MacBook Neo support from this host.

## Decision proposal for the coordinator

Proposed shared decision-log entry: **defer the direct-sclang versus helper
choice until matching 3.14.1 runtime probes are available**. Context:
runtime binaries and a Windows target were unavailable; alternatives are
selecting a direct path from host tools/source inspection, adding the planned
headless helper without evidence, or leaving the transport gate open.
Rationale: only the last option avoids turning unverified platform assumptions
into product architecture. Consequence: provider transport and credential
storage remain unimplemented and unverified; a runtime-capable follow-up is
required before phase 0 can close.
