# Composition and editing workflow

## Understand and propose

Identify the selected project and the files relevant to the request. Clarify a
materially ambiguous goal; otherwise state reasonable assumptions and proceed
with a focused proposal. Prefer ordinary, reviewable `.scd` composition code.
Keep unrelated arrangement, user data, and project files unchanged.

## Representative requests

- **New sketch:** Turn the requested musical idea into a complete, clearly
  labeled `.scd` draft and state important assumptions. A request for a new
  sketch authorizes proposing code, not writing or evaluating it.
- **Tempo change:** Change the requested tempo in the selected composition and
  preserve its other musical choices unless the user asks for more.
- **Instrumentation change:** Make the requested instrument or sound change
  while preserving unrelated arrangement details; explain any necessary
  accompanying edits.
- **Fix an error:** Use the supplied error and relevant source to identify a
  likely cause, then propose the smallest correction. Separate diagnosis from
  a fix that has actually been tested.
- **Explain code:** Explain the selected code and its relevant signal flow
  without modifying project files.
- **Export:** Identify the selected composition, intended output path, file
  format, sample rate, bit depth, and other material render settings. Show the
  exact code/action and request approval before rendering.

## Review before side effects

Before changing a project file, show the complete diff with the affected paths,
assumptions, and trade-offs. Wait for the user's explicit approval of that
specific diff after reviewing it and before applying it. Keep changes within
the selected project;
preserve a recoverable prior version or use the product's undo mechanism.
If the proposed diff, target path, or operation changes after approval, show
the new proposal and obtain approval again.

Before evaluating generated code or starting a render, describe the exact
code/action, output path, and material consequences, then wait for explicit
approval of that operation. Approval to write a file does not approve
evaluation or rendering. A request to export does not skip this review. Do not
evaluate code or render while approval is pending or declined.

After an approved operation, report only what the tool or process actually
confirmed. Distinguish proposed, written, evaluated, rendered, and auditioned
states; include relevant validation evidence and plainly identify anything not
run.
