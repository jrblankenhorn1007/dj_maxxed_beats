MaxxedBeats AI assistant for SuperCollider - Windows 10/11 (x64)
=================================================================

The standard assistant needs no Python, CMake, or compiler. GitHub Copilot is
an optional provider and needs the additional runtime described below.

  MaxxedBeats\   the assistant (SuperCollider Quark, with agent\*.md)
  ChaosOsc\      the ChaosOsc UGen plugin (ChaosOsc.scx, prebuilt with MSVC)
  install.ps1    copies both into %LOCALAPPDATA%\SuperCollider\Extensions
  uninstall.ps1  removes them again

Requirements: Windows 10 (version 1803 or newer) or Windows 11, 64-bit, and
SuperCollider 3.14.1 (64-bit) from https://supercollider.github.io/downloads.
curl.exe and PowerShell, which the assistant uses, are part of Windows.

Install
  1. Right-click the zip > Extract All... (do not run it from inside the zip).
  2. Open the extracted folder, click the address bar, type
         powershell -ExecutionPolicy Bypass -File install.ps1
     and press Enter. It prints where it installed and the next steps.
  3. Start SuperCollider (or, if it was open: Language > Recompile Class
     Library), then evaluate:   s.reboot;   and   MaxxedBeats.gui;

Use: in the window, "Choose your DJ" (Mock DJ works offline; for OpenAI or
Anthropic paste your API key in Keys & Privacy - it is stored in Windows
Credential Manager, never in files). The GitHub Copilot sign-in row appears
beside those API-key rows and does not ask for a key. Renders are written to
<project>\renders.

Optional GitHub Copilot setup
  1. Install Python 3.11 or newer and the official GitHub Copilot CLI:
       https://docs.github.com/en/copilot/how-tos/copilot-cli/install-copilot-cli
     Make sure "python --version" reports 3.11 or newer and "copilot" is on
     PATH, then restart SuperCollider so it inherits the updated PATH.
  2. In PowerShell, install the optional SDK dependency:
       python -m pip install -r "$env:LOCALAPPDATA\SuperCollider\Extensions\MaxxedBeats\Data\copilot\requirements.txt"
     If you installed into a custom Extensions folder, adjust that path.
  3. In MaxxedBeats, choose GitHub Copilot, open Keys & Privacy, and click
     "Sign in to GitHub Copilot..." in its provider row.

Python and the Copilot CLI are not needed for Mock, OpenAI, or Anthropic.

Uninstall: run   powershell -ExecutionPolicy Bypass -File uninstall.ps1
from the same folder, then recompile the class library. Only folders that
install.ps1 created (they contain a marker file) are ever replaced or removed.

More: docs/USER_GUIDE.md in the source repository ("Windows (no developer
tools)").
