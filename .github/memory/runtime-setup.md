# Runtime setup memory

### Persist executable paths for GUI-launched runtimes
- **Rule:** Persist resolved paths for external executables launched by a GUI
  host, and reload them at launch instead of relying on the GUI's inherited
  `PATH`.
- **Why:** SCIDE could not see a per-user Copilot CLI absent from its `PATH`;
  the provider reloads saved Python and CLI paths for each request, and tests
  cover discovery outside `PATH` and setup refresh without restarting SCIDE.
  See the [provider](../../extension/Classes/Providers/MBCopilotProvider.sc),
  [bridge](../../extension/Data/copilot/bridge.py), and
  [Copilot tests](../../tests/test_mb_copilot.py).
- **Scope:** External runtimes launched from SuperCollider GUI processes.

### Verify downloaded command-line runtimes before extraction
- **Rule:** Pin the upstream release, verify its platform-specific SHA-256
  before unpacking, and extract only the expected executable.
- **Why:** The Copilot installer rejects checksum mismatches before
  installation; tests cover both verified installation and mismatch
  rejection. See the
  [installer](../../extension/Data/copilot/setup_copilot.py) and
  [setup tests](../../tests/test_mb_copilot_setup.py).
- **Scope:** Installers that download external CLI binaries.

### Check required packages against distro sources
- **Rule:** Distinguish package-index refresh failures from unavailable
  required packages, and offer a distribution-supported source or OS upgrade
  rather than silently adding an untrusted repository.
- **Why:** Ubuntu 22.04's default APT sources may not provide the required
  Python 3.11 packages; the Linux setup gives actionable recovery steps and
  has a regression test for this case. See the
  [Linux setup helper](../../extension/Data/copilot/setup-copilot.sh) and
  [setup tests](../../tests/test_mb_copilot_setup.py).
- **Scope:** User-facing Linux setup for required runtimes.

### Point runtime errors at the platform setup action
- **Rule:** When a GUI-launched provider cannot start because its runtime
  prerequisites are missing, name the OS-specific setup launcher and the
  immediate action instead of only listing version requirements.
- **Why:** The generic Copilot Python/SDK error did not identify the existing
  macOS, Linux, or Windows helper. The bridge now names each launcher, and
  tests verify the platform messages reach the SuperCollider provider error
  callback. See the
  [bridge](../../extension/Data/copilot/bridge.py) and
  [Copilot tests](../../tests/test_mb_copilot.py).
- **Scope:** Optional external runtimes launched from GUI applications.
