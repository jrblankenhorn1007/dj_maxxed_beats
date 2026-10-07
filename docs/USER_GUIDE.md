# MaxxedBeats user guide

MaxxedBeats is an AI music assistant that runs inside SuperCollider. You
describe music in a window opened from SCIDE, the provider and model you
choose propose a musical plan and changes to your `.scd` project, you review
and approve them, and SuperCollider renders the result offline to a WAV file.

- [Install](#install)
  - [Windows (no developer tools)](#windows-no-developer-tools)
- [Open the assistant](#open-the-assistant)
- [Choose your DJ: provider and model](#choose-your-dj-provider-and-model)
- [API keys: add, replace, validate, remove](#api-keys-add-replace-validate-remove)
- [Privacy](#privacy)
- [API cost, usage, and credits](#api-cost-usage-and-credits)
- [Compose, review, and render](#compose-review-and-render)
- [Variation sessions](#variation-sessions)
- [Troubleshooting](#troubleshooting)
- [Update and uninstall](#update-and-uninstall)

## Install

On Windows you can skip everything below and use the ready-made package:
see [Windows (no developer tools)](#windows-no-developer-tools).

Installing from source needs these prerequisites:

| | macOS (Apple Silicon or Intel) | Windows 10/11 x64 | Linux |
| --- | --- | --- | --- |
| SuperCollider | 3.14.1 | 3.14.1 | 3.14.1 |
| Python | 3.9 or newer | 3.9 or newer (`py`/`python`) | 3.9 or newer |
| CMake | 3.16+ (`brew install cmake`) | 3.16+ (`winget install Kitware.CMake`) | 3.16+ (`sudo apt install cmake`) |
| C++17 compiler | `xcode-select --install` | Visual Studio 2022 (or Build Tools) with "Desktop development with C++" | `build-essential` or clang |

From a checkout of this repository:

```sh
python3 scripts/install_maxxedbeats.py --dry-run   # preview, changes nothing
python3 scripts/install_maxxedbeats.py
```

(On Windows use `python` or `py` instead of `python3`.) The installer builds
the ChaosOsc plugin and copies the MaxxedBeats Quark (classes, help, agent
instructions) into SuperCollider's user Extensions folder:

- macOS: `~/Library/Application Support/SuperCollider/Extensions`
- Windows: `%LOCALAPPDATA%\SuperCollider\Extensions`
- Linux: `~/.local/share/SuperCollider/Extensions` (or `$XDG_DATA_HOME/...`)

It creates `MaxxedBeats/` and `ChaosOsc/`, each with a hidden install marker.
Folders without that marker are never replaced unless you pass `--force`, and
both folders are checked before anything is built or copied. Use
`--extensions-dir DIR` for another location.

Afterwards, in SCIDE:

1. **Language > Recompile Class Library** (or `thisProcess.recompile`).
2. Reboot the audio server so it loads ChaosOsc: `s.reboot`.

The installer warns if another copy of MaxxedBeats is in your Extensions
folder or on an include path in `sclang_conf.yaml`; remove duplicates, or
sclang reports duplicate classes.

### Windows (no developer tools)

`MaxxedBeats-Windows-x64.zip` contains the MaxxedBeats Quark (with its agent
instructions), the ChaosOsc plugin prebuilt with MSVC (`ChaosOsc.scx`),
`install.ps1`, `uninstall.ps1`, and a short `README.txt`. You need no
Python, CMake, or compiler. It is built by the **Assistant Tests** workflow
(job "Windows package") on every push to this repository; open a successful
run on GitHub's **Actions** tab and download the artifact
**MaxxedBeats-Windows-x64** (GitHub delivers it as
`MaxxedBeats-Windows-x64.zip`).

Requirements: Windows 10 version 1803 or newer, or Windows 11 (64-bit), and
SuperCollider 3.14.1 for Windows (64-bit) from
<https://supercollider.github.io/downloads>. The assistant uses `curl.exe`
and Windows PowerShell, which are part of Windows.

Step by step:

1. Install SuperCollider 3.14.1 and start it once, then close it.
2. Download `MaxxedBeats-Windows-x64.zip`, right-click it, choose
   **Extract All...**, and open the extracted folder (it contains
   `install.ps1`). Do not run anything from inside the zip.
3. Click the folder's address bar, type
   `powershell -ExecutionPolicy Bypass -File install.ps1` and press Enter.
   The script copies `MaxxedBeats\` and `ChaosOsc\` into
   `%LOCALAPPDATA%\SuperCollider\Extensions` and prints the next steps. It
   refuses to touch a `MaxxedBeats` or `ChaosOsc` folder there that it did
   not install (no marker file) and then changes nothing.
4. Start SuperCollider (if it is already open: **Language > Recompile Class
   Library**), then evaluate `s.reboot;` and `MaxxedBeats.gui;`.
5. In the window, choose **Mock DJ (offline)** to try it without a key, or
   OpenAI / Anthropic after saving your API key on **Keys & Privacy**. Keys
   are kept in Windows Credential Manager (entries `MaxxedBeats:openai` and
   `MaxxedBeats:anthropic`), never in files.

To update, extract the newer zip and run its `install.ps1` again (it replaces
the marked folders). To uninstall, run
`powershell -ExecutionPolicy Bypass -File uninstall.ps1` from the extracted
folder, then recompile the class library. Either script only ever replaces
or removes folders carrying the MaxxedBeats install marker, so it is
compatible with `scripts/install_maxxedbeats.py`.

How it works on Windows: provider requests run `%SystemRoot%\System32\curl.exe`
(TLS verified against the Windows certificate store) through a small
PowerShell helper that reads the key from Credential Manager and writes it
only to curl's standard input. Approved renders run a separate `sclang.exe`
and `scsynth.exe` (with a cleared environment and their own class library
configuration, so your startup file and other Extensions are not loaded)
and use the ChaosOsc you installed. CI verifies all of this on a hosted
Windows runner; checking it on a physical PC (sound and window appearance)
is still a manual step.

## Open the assistant

```supercollider
MaxxedBeats.gui;
```

Evaluating it again brings the open window to the front. The help browser
has a **MaxxedBeats** page and a **MaxxedBeats Assistant** guide.

The window shows, at the top: the project folder, **Choose your DJ**, the
status line with progress and **Stop request**, any error (with **Dismiss**),
and any confirmation request. Below are four tabs: **Compose**,
**Variations**, **Keys & Privacy**, and **Usage**.

## Choose your DJ: provider and model

1. Pick a provider: OpenAI, Anthropic, **GitHub Copilot**, or **Mock DJ (offline)**. The mock
   needs no key, never uses the network, and costs nothing: it answers with a
   deterministic ChaosOsc sketch (it does not understand your prompt), which
   is handy for trying the whole workflow.
2. Press **Refresh models** to fetch the provider's model list.
3. Pick a model. The window always shows the exact **Provider id** and
   **Model id** the next request will use, and each provider remembers its
   own model.

   ### GitHub Copilot subscription

   Choose **GitHub Copilot** to use your GitHub Copilot subscription instead of
   paying through an OpenAI or Anthropic API key. This is Copilot, not the separate
   GitHub Models API.

   The **Keys & Privacy** tab shows Copilot's sign-in row alongside the
   OpenAI and Anthropic API-key rows. Install the [official GitHub Copilot
   CLI](https://docs.github.com/en/copilot/how-tos/copilot-cli/install-copilot-cli)
   if it is not already installed. Copilot also needs Python 3.11+ and the
   optional SDK dependency listed in the installed extension's
   `Data/copilot/requirements.txt`; install it with
   `python -m pip install -r <path-to-that-file>`. OpenAI, Anthropic, and
   Mock do not need Python or the Copilot SDK. Click **Sign in to GitHub
   Copilot...** in its row and complete GitHub's browser sign-in.
   The runtime may need its own sign-in even if you are already signed in to the
   VS Code Copilot extension; MaxxedBeats does not extract VS Code credentials.
   Then press **Refresh models**, choose an available model, and send your prompt.

   Copilot's models come from the runtime, not a hard-coded list. The selected
   model is never silently substituted. Subscription allowances and charges are
   managed by GitHub; MaxxedBeats does not pretend Copilot requests have OpenAI's
   API price. Unavailable USD and app-credit estimates stay labelled unavailable.
   The provider proposes code only: runtime tools and permission requests are
   disabled, and the existing review/apply/render approvals still apply.

MaxxedBeats never switches provider or model on its own:

- Models the assistant cannot use are labelled **[unavailable: reason]** and
  cannot be selected.
- If your saved model is no longer offered, it stays selected, is labelled
  **UNAVAILABLE**, and requests are blocked until you choose another model.
- If a refresh fails, the error is shown and the cached list stays visible,
  labelled as possibly stale.

## API keys: add, replace, validate, remove

Open **Keys & Privacy**. OpenAI and Anthropic each have their own API-key row;
GitHub Copilot has a sign-in row alongside them and does not need an API key.
Only configure the provider you use.

- **Add or replace:** paste the key into the field and press **Save /
  replace**. The field never shows the key; only a count of `*` characters
  appears. Characters can only be appended: if you make a mistake, press
  **Clear** and paste again.
- **Validate:** asks the provider whether the stored key works by listing its
  models (a free request). A rejected key is shown as *invalid*; with no key
  stored you get an auth error and nothing is sent.
- **Remove:** press **Remove...** and confirm. Requests to that provider then
  fail until you add a key again.

Keys are stored in your operating system's credential store: macOS Keychain,
Windows Credential Manager, or the Linux Secret Service (for example GNOME
Keyring or KWallet). They are never displayed, logged, posted to the post
window, or written to settings, project files, or render metadata. Error
messages are redacted.

Get keys from your provider account: OpenAI (platform.openai.com, API keys)
or Anthropic (console.anthropic.com, API keys). Use a key with a spending
limit you are comfortable with.

## Privacy

- Your prompt, the conversation so far, and **only the project files you
  select** under *Context files* are sent to the provider you chose. With no
  file selected, only the prompt and conversation are sent.
- Nothing is sent anywhere else. There is no telemetry. Usage history stays
  on your computer.
- Settings (not secrets) are stored under SuperCollider's user configuration
  folder in `MaxxedBeats/`. Backups and variation sessions live in your
  project's `.maxxedbeats/` folder; renders go to `renders/` with a JSON
  metadata file that never contains keys.
- The provider's own data-retention policy applies to what you send.

## API cost, usage, and credits

Model requests may incur charges on **your** provider account. After each
request the Compose tab and the **Usage** tab show:

- provider and model, and the input, output, and cached-input token counts
  reported by the provider (`?` when the provider did not report one);
- the **estimated** cost in US dollars, from a versioned rate table whose
  version is shown;
- **credits**: an informational estimate at 100 credits per estimated US$1.
  Credits are not a balance, a purchase, an invoice, or an exact bill.

Free models (such as the offline mock) show **no cost (US$0)**. If the rate
for a model is missing, USD and credits are shown as
**unavailable** and the rates as **MISSING**; if rates are outdated they are
labelled **STALE**. Unknown cost is never shown as zero. The Usage tab also
shows the current session's totals and the local history, which **Clear
history...** deletes (after confirmation). Check your provider's billing page
for actual charges.

## Compose, review, and render

1. **Open a project:** press **Choose...** (or type a folder path and press
   **Open**). A project is a folder of `.scd` files; the assistant never
   modifies files outside it.
2. **Ask:** select context files, type a prompt, and press **Send to DJ**.
   **Stop request** cancels a running request.
3. **Review:** the proposed musical plan (with the DJ's assumptions,
   uncertainty, and questions) and the diff of every file change appear.
   *PENDING REVIEW: nothing has been written yet.* If the DJ suggests an
   entry file or render length, the render panel adopts it.
4. **Approve or reject:** **Approve and apply...** asks you to confirm, saves
   a backup, then writes the files. **Reject** discards the proposal; nothing
   is written. While a proposal is pending, approve or reject it before
   sending another prompt.
5. **Undo:** **Undo last apply...** (after confirmation) restores the most
   recent backup.
6. **Render:** choose the entry file, length in seconds, sample rate, and
   channels, then press **Render...** and confirm. Generated code is evaluated
   only in a separate headless sclang process (never in your interpreter) and
   rendered offline by scsynth, so no audio device is needed. When it
   finishes, the window shows the new WAV file, its duration and format, and
   audio checks (non-finite samples, silence, clipping, duration); warnings
   are labelled.
   **A separate process is not a sandbox:** approved composition code has
   your user privileges, including filesystem, network, and credential-store
   access. Review the code before approving execution.
7. **Listen:** **Play preview** plays the rendered file on your running
   server (boot it first with `s.boot`); **Stop** ends playback. **Reveal
   file** shows the WAV in Finder, Explorer, or your file manager.

Errors (API, network, parsing, rendering) appear in red at the top and in the
conversation. A failed action is never reported as completed.

## Variation sessions

On **Variations**, type a variation prompt, choose how many candidates (1 to
4), and press **Start session**. Starting a session generates code only; it
does not authorize execution of code you have not seen. Each candidate is one provider request with its own
fixed seed. Its code, seed, settings, render, and checks are kept in an
isolated folder under `.maxxedbeats/sessions/`; failed candidates are listed
as FAILED with the reason. **Stop** ends the session early. Select a candidate
to review its plan, diff, and full generated code. **Render selected...**
requires approval for that specific candidate after review (with the length,
rate, and channels from the Compose tab). It is not a sandbox and has the
same user privileges described above. **Audition
selected** plays it, and **Apply selected...** (after confirmation, with a
backup) applies that candidate's changes to your project. Your project is
unchanged until you apply one.

## Troubleshooting

| Symptom | What to do |
| --- | --- |
| `MaxxedBeats` is not defined | Run the installer, then recompile the class library. |
| "missing classes" error in the window | The installation is incomplete; re-run `python3 scripts/install_maxxedbeats.py` (Windows package: `install.ps1`) and recompile. |
| Windows: `install.ps1` "cannot be loaded because running scripts is disabled" | Start it as shown: `powershell -ExecutionPolicy Bypass -File install.ps1` (this changes no system setting). |
| Windows: "Could not ... in Windows Credential Manager" | Make sure you are signed in to a normal Windows user account; the key store is per user. |
| Duplicate class errors after recompiling | Remove other MaxxedBeats copies or include paths named by the installer's warnings. |
| "No API key is stored" / auth error | Save the key on **Keys & Privacy**, then **Validate**. Check the key has API access and billing enabled. |
| Model unavailable | Press **Refresh models** and select a listed model. |
| Model refresh failed / stale list | Check your connection and key; the cached list is shown until a refresh succeeds. |
| Rate limit (`rateLimit`) | Wait and retry, or check your provider plan's limits. |
| Render failed | Read the error; fix the composition (or Undo) and render again. Make sure ChaosOsc is installed and the class library was recompiled. |
| Play preview fails | Boot the server (`s.boot`). The WAV is already rendered; you can also open it via **Reveal file**. |
| `ChaosOsc` not found by scsynth | Reboot the server after installing (`s.reboot`). |
| Installer: "refusing to overwrite" | A folder not created by the installer exists; move it away or re-run with `--force`. |
| Installer: CMake or compiler missing | Install the prerequisites listed in [Install](#install). |

## Update and uninstall

To update, pull the latest source and run the installer again; it replaces
the marked folders. Then recompile the class library and reboot the server.

To uninstall:

1. Optionally remove your API keys first (**Keys & Privacy > Remove...**).
   Uninstalling does not delete keys from the OS credential store; you can
   also delete the entries named for MaxxedBeats in Keychain Access, Windows
   Credential Manager, or your Linux keyring.
2. Close the assistant window and run:

   ```sh
   python3 scripts/install_maxxedbeats.py --uninstall --dry-run   # preview
   python3 scripts/install_maxxedbeats.py --uninstall
   ```

   This removes only the marked `MaxxedBeats/` and `ChaosOsc/` folders.
3. Recompile the class library and reboot the server.

Your projects, renders, backups, and the settings folder
(`MaxxedBeats/` under SuperCollider's user configuration folder) are left in
place; delete them yourself if you no longer need them.
