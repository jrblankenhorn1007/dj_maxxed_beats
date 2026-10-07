MaxxedBeats AI assistant for SuperCollider - Windows 10/11 (x64)
=================================================================

This zip contains everything; you do NOT need Python, CMake, or a compiler.

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
Credential Manager, never in files). Renders are written to <project>\renders.

Uninstall: run   powershell -ExecutionPolicy Bypass -File uninstall.ps1
from the same folder, then recompile the class library. Only folders that
install.ps1 created (they contain a marker file) are ever replaced or removed.

More: docs/USER_GUIDE.md in the source repository ("Windows (no developer
tools)").
