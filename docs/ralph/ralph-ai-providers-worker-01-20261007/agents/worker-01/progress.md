# worker-01 progress — provider layer

Branch `ralph/ai-providers-worker-01-20261007` (base 961b1c2). Design and
decision proposals: [docs/design/providers.md](../../../../design/providers.md).

## TDD log

- Red: wrote `tests/test_mb_providers_{core,http,keychain}.py` + harness and
  loopback fake server first; all failed (classes absent).
- Green: implemented `MBJSON`, `MBRedact`, `MBProviderPaths`, `MBProcess`,
  `MBHttp`, `MBCredentialStore` (+ Keychain/SecretService/Windows/Fake),
  `MBProvider`, `MBOpenAIProvider`, `MBAnthropicProvider`, `MBMockProvider`,
  `MBProviderRegistry`, `MBRateTable`, `MBUsageMeter`, `MBModelCatalog`,
  `Data/provider-rates.json`, `Data/windows/MaxxedBeatsCredential.ps1`.
- Found and worked around an sclang 3.14 VM issue (exception during argument
  evaluation corrupts later calls in Routines) — regression covered by the
  malformed-JSON test.

## Verification

- `python3 -m unittest discover -s tests -p 'test_mb_providers_*.py' -v`
  (SCLANG set): 17 tests OK (~36 s).
- Live non-provider TLS probe from sclang (example.com 200; badssl
  self-signed/expired/wrong-host rejected with curl 60).
- Full gate `scripts/run_headless_tests.sh` (SCLANG/SCSYNTH = SC 3.14.1 app): exit 0, 115 tests OK (1 pre-existing skip), 129 s.
- No provider API was called; no real key was used; login keychain and the
  user keychain search list untouched (test asserts the latter).
