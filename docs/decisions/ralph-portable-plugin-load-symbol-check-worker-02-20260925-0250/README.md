# Branch decisions

- **Exact branch:** `refs/heads/ralph/portable-plugin-load-symbol-check-worker-02-20260925-0250`
- **Branch slug:** `ralph-portable-plugin-load-symbol-check-worker-02-20260925-0250`
- **Run/task:** `ralph-cross-platform-review-luna-20260925-0250` /
  `portable-plugin-load-symbol-check`
- **Worker:** `worker-02 / Plugin symbol portability`
  (`runtime_agent_id: copilotcli:/a17ae5a3-53fe-4381-a9fd-f590086cec29`)
- **Base:** `0736add11eae7b7f745d7b7bf9806c116d72eed6`
- **Implementation commit:** `b1d68a2a2641a7e521f3004107d593ee7875b1d8`
  (`Support portable ChaosOsc plugin load symbols`).
- **PR record:** [worker-02 pending PR](./agents/worker-02/pr-pending.md)

The worker independently reviewed the plugin source (`PluginLoad(ChaosOscUGens)`),
smoke script, implementation-plan platform targets, and NRT assertion. The
network-free test
`PYTHONDONTWRITEBYTECODE=1 python3 tests/test_plugin_smoke_symbol_check.py`
then confirmed that the pre-change smoke script accepted Darwin `_load` but
rejects exact unprefixed `load` output for both ELF and Windows x64 fixtures.
This observed Red, not the coordinator's suspicion, confirms the defect.

**Decision:** Match both exact symbols `_load` and `load` from the existing
`nm -gU` output, with no host-specific branch; reject substring lookalikes.
Update the NRT assertion to accept either success message. A platform-specific
parser or keeping only `_load` were rejected because neither is needed to
recognize the two C-linkage spellings, and the latter leaves the confirmed
cross-platform defect. Consequence: the shell-level mocked test verifies
checker logic only; native ELF/Windows builds and runtime remain unverified.
