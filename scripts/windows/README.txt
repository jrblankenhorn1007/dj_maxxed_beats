MaxxedBeats for SuperCollider - Windows 10/11 (x64)
===================================================

This package includes the assistant and the prebuilt ChaosOsc audio plugin.
You do not need Python, CMake, a compiler, or Terminal commands to install it.

Before you start
  - Windows 10/11, 64-bit.
  - SuperCollider 3.14.1, 64-bit: https://supercollider.github.io/downloads
  - To use GitHub Copilot, an active Copilot subscription and an internet
    connection. Copilot uses GitHub sign-in; it does not need an API key.

Install
  1. Download MaxxedBeats-Windows-x64.zip and right-click it > Extract All.
     Do not run files from inside the zip.
  2. Open the extracted folder and double-click Install-MaxxedBeats.cmd.
     Do not type a command.
  3. The installer copies MaxxedBeats and ChaosOsc into your SuperCollider
     Extensions folder. It then asks whether you want to set up Copilot.
     Choose Y to let WinGet install Python 3.13 and the official GitHub
     Copilot CLI if needed. This also creates MaxxedBeats' private SDK
     environment. Choose N to skip Copilot; Mock DJ, OpenAI, and Anthropic
     remain available.
  4. If Windows says WinGet is missing, install Microsoft App Installer from
     https://aka.ms/getwinget, then double-click Install-MaxxedBeats.cmd again.
     The setup does not ask you to paste or save a GitHub token.
  5. Start or restart SuperCollider. In SCIDE choose Language > Recompile
     Class Library, then reboot the audio server so it loads ChaosOsc.
  6. In SCIDE choose File > Open and open
     %LOCALAPPDATA%\SuperCollider\Extensions\MaxxedBeats\LaunchMaxxedBeats.scd.
     Click its single line and press Ctrl+Enter. This opens the MaxxedBeats
     window; you do not need to type code into Terminal.
  7. In MaxxedBeats set the provider to GitHub Copilot. Open the Keys & Privacy
     tab, click Sign in to GitHub Copilot... beside its row, and finish the
     browser sign-in. Then choose Refresh models.

The Copilot virtual environment is stored in
%LOCALAPPDATA%\MaxxedBeats\Copilot. Its non-secret executable paths are saved
in %APPDATA%\SuperCollider\MaxxedBeats\copilot-runtime.json. The Copilot CLI
stores its own sign-in; MaxxedBeats does not use VS Code credentials.

Update: extract the newer zip and double-click Install-MaxxedBeats.cmd again.
Only marked MaxxedBeats/ChaosOsc folders are replaced. If you skipped Copilot
and want to add it later, double-click Setup-Copilot.cmd in the extracted zip.

Uninstall: double-click Uninstall-MaxxedBeats.cmd from the extracted folder,
then recompile the class library. This removes the marked MaxxedBeats and
ChaosOsc folders.
It keeps your projects, renders, settings, Python, Copilot CLI, and saved
credentials; remove Python/CLI separately from Windows Settings if you no
longer want them.

If the one-click installer is unavailable, install.ps1 and setup-copilot.ps1
are included for Windows support staff.
