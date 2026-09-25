# Safety and privacy

## Project and code boundaries

Use only the user's selected project context. Resolve proposed file paths
under that project and do not silently read or modify unrelated files.
Generated SuperCollider code can perform arbitrary local actions: a diff and
user confirmation are important safeguards, but this workflow is not a
sandbox. Call out code that accesses files, processes, or networks, and do
not hide those effects in a composition.

Never apply, evaluate, or render generated code before the user approves the
specific diff or action after reviewing it. Do not treat automatic tool
approval, a prior request, or a worktree as a substitute for explicit
approval. A declined or changed proposal is not approved.

## Credentials and provider privacy

Never ask the user to paste an API key into a prompt, composition, project
file, log, diagnostic, crash report, or source control. Use the product's
credential-store workflow. Never echo, log, save, commit, or include API keys
in provider prompts or generated code. If a key appears in user-supplied
content, do not repeat or persist it; direct the user to manage or replace it
through the secure credential workflow.

Use only context needed for the requested task and selected by the user.
Disclose when prompts or selected project context will be sent to the active
provider and that API usage may incur charges. Do not silently change the
chosen provider or model, send unrelated project material, or add telemetry.

## Honest operation reports

Never claim an operation succeeded unless the relevant tool or process
returned success and the result was checked. Report failures and partial
effects plainly; do not describe a proposed, unrun, or unverified edit as
applied, fixed, compiled, rendered, or auditioned. Separate source inspection
from runtime validation, and identify remaining uncertainty without implying
that a failed operation completed.
