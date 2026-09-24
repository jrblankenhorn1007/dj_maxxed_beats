---
name: tdd
description: Use for every behavior-changing implementation or bug fix. Drive the change through test-first Red-Green-Refactor, with evidence for each stage.
---

# Test-Driven Development

Use this skill before writing production code for a behavior change or bug fix.
The project implementation prompt requires this skill on every development
iteration.

## Red-Green-Refactor

1. **Select one behavior.** Choose the smallest observable behavior from an
   acceptance criterion. State the expected result and identify the narrowest
   relevant test.
2. **Red: write the test first.** Add or change the test before production
   code. Run it and confirm it fails because the behavior is missing or wrong.
   Record the command and the meaningful failure in `RALPH_PROGRESS.md`.
3. **Green: implement minimally.** Make only the production change needed to
   pass that test. Run the new test and the smallest relevant regression set.
4. **Refactor.** Improve implementation and test structure without changing
   behavior. Re-run the targeted tests; keep the relevant suite green.
5. **Repeat.** Select the next behavior and begin with a new failing test.

Do not count a syntax error, missing dependency, broken fixture, or test-runner
failure as the Red result. Fix the test setup, establish the baseline, then
re-run the test so the expected behavior itself is what fails. Never weaken or
delete an assertion merely to get Green.

## Project-specific test guidance

- **C++ sound-design UGens:** test pure DSP calculations and input bounds where
  practical. Use fixed seeds and short deterministic renders. Add SuperCollider
  NRT integration coverage for loading the plugin, using its sclang class, and
  writing an audio file. Check finite output, duration, and meaningful signal
  properties; use tolerances for platform-level floating-point differences.
- **Provider/model adapters:** test request/response mapping, streaming,
  model-list failures, stale pricing, and malformed responses with fakes or
  fixtures. Never require a live OpenAI/Anthropic call or real API key in unit
  tests.
- **Credits and cost:** write failing tests for token-usage mapping, versioned
  model-rate calculations, rounding, per-session aggregation, and missing-rate
  behavior before implementing the calculator or UI. Unknown cost must remain
  unavailable, not become zero.
- **Credentials and privacy:** inject credential-store interfaces and use test
  doubles. Assert that keys never enter logs, project files, prompts, or
  committed fixtures.
- **In-app variation loop:** use fixed seeds and a small candidate limit.
  Test early stop, candidate isolation, and that the original project remains
  unchanged unless the user confirms applying a candidate.
- **GUI/manual behavior:** automate state and action behavior where the
  available UI test framework permits. For GUI-affecting changes, launch the
  actual app from SCIDE, exercise the visible workflow, capture its native
  window, and inspect the screenshot. Before completion, run the full scenario
  from `VISUAL_TEST_PLAN.md` on Windows 10 x64 and an actual MacBook Neo.
  Prefer OS accessibility automation; only add a small test-only CLI or
  in-process driver if needed, and do not add an unauthenticated production
  control endpoint. Use mock providers and safe fixtures, never real API keys.
  Record platform versions and screenshot artifact references in
  `RALPH_PROGRESS.md` and `implementation_status.md`. Manual listening
  complements, but does not replace, deterministic tests.

Use the repository's existing test/build ecosystem where possible. If a
required behavior has no test harness, first write a failing executable check
or test specification and establish the smallest maintainable test setup; do
not skip test-first work because the project is new. Keep every test isolated,
repeatable, and free of external billing/network dependencies.

## Iteration evidence

For each behavior-changing slice, include in `RALPH_PROGRESS.md`:

- the Red command and why it failed as expected;
- the Green command and result;
- the post-refactor verification result;
- any platform or environment coverage that remains unverified.

Commit the tests with the implementation and the iteration's decision-log
entry. Never claim TDD evidence for a test that was not actually run.

## Reference

This workflow follows Martin Fowler's explanation of the test list and
Red-Green-Refactor cycle:
<https://martinfowler.com/bliki/TestDrivenDevelopment.html>
