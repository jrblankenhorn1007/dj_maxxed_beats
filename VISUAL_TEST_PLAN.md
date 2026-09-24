# Visual Application Test Plan

The Ralph loop's final acceptance gate is to launch the real SuperCollider
application workflow, exercise it, capture its actual window, and inspect the
screenshots. A passing build, headless test, mocked widget, or textual log is
not visual confirmation.

## When to run

- For each iteration that changes the GUI or a user-visible workflow, run the
  relevant visual smoke check on the available target platform and record the
  result.
- Before reporting `RALPH_COMPLETE`, run the full scenario below on Windows 10
  x64 and on an actual MacBook Neo. Generic macOS/Apple Silicon testing does
  not establish MacBook Neo compatibility.
- If a required device or desktop-capture facility is unavailable, record the
  exact limitation in `RALPH_PROGRESS.md` and `implementation_status.md`.
  Do not claim visual verification or mark the project complete while a
  required platform gate is unverified.

## Full visual smoke scenario

Use a clean test project and the packaged extension/plugin install path. Keep
the app GUI visible and launch it from SCIDE through its documented entry
point; do not substitute a standalone mock window.

1. Start SuperCollider/SCIDE and open the agent GUI. Confirm the window paints,
   controls are legible, and no startup/load errors or missing-plugin state is
   hidden behind the window.
2. Use a deterministic mock provider and a reviewed fixture composition. Do
   not enter real OpenAI/Anthropic credentials or make billable API calls.
   Confirm the selected provider/model and a representative request/response
   are visible.
3. Request a small composition edit. Inspect the displayed diff, exercise the
   approval/cancel choice in the real UI, and confirm the original project is
   preserved until approval.
4. Approve the safe fixture change in the isolated test project. Render it
   using the packaged SuperCollider plugin in NRT mode. Confirm the UI reports
   success and independently verify that the WAV exists, is non-empty, and
   matches the expected duration/format.
5. Confirm the usage view renders deterministic mock token counts, estimated
   USD, and informational credits with the estimate/pricing labels. Exercise
   at least one relevant error state (for example, provider unavailable or
   render failure) and ensure it is visible and not reported as success.
6. Once implemented, exercise the bounded variation control and verify the
   visible candidate count/stop state without exceeding the configured limit.

Do not bypass confirmation safeguards to make automation easier. Use a
reviewed, harmless fixture and a disposable test project.

## Driving the visible application

First inventory existing SuperCollider/SCIDE launch, scripting, and GUI test
capabilities, plus the platform's accessibility automation. Prefer those
capabilities to a new control service. Any automation must exercise the actual
application widgets and controller path while the real window is displayed;
controller/unit tests alone do not satisfy this plan.

If native accessibility automation cannot reliably run the scenario, add the
smallest test-only CLI or in-process test driver that launches the real GUI,
selects a deterministic mock provider, and sends a bounded set of named test
actions through the same application code used by the UI. Do not add a
permanently enabled or unauthenticated production HTTP/OSC control endpoint.
If a local IPC bridge is unavoidable, require explicit test mode, bind only to
loopback, use a per-run capability/token, restrict commands to the test
scenario, prohibit arbitrary sclang evaluation, and disable the bridge in
release builds.

The driver controls setup/actions; it must not fabricate screenshots or
replace the visible GUI with a mock. Capture the actual native application
window using an available platform screen-capture tool, then inspect the image
visually for layout, blank/error states, clipping/overlap, unreadable labels,
and the expected interaction result. If the agent environment cannot capture
and inspect a native window, report that limitation rather than inferring
visual success from logs.

## Evidence to retain

For each tested platform, record in `RALPH_PROGRESS.md` and
`implementation_status.md`:

- device/model, OS version, SuperCollider version, and build/plugin revision;
- scenario steps and whether the real GUI was launched from SCIDE;
- pass/fail results for the visual checks and independent render-file checks;
- paths or links to fresh screenshots and test artifacts, plus any failure
  logs.

Store screenshots as local or CI test artifacts by default, not as committed
source files. Inspect/redact screenshots so they contain no API keys, private
project data, or unrelated personal information.
