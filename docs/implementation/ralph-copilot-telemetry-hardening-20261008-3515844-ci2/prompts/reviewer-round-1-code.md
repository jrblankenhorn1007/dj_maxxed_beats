# Code reviewer prompt — round 1

Use the GPT-6.1 Luna model. Review the exact current PR base/head pair supplied
at dispatch; record both full SHAs and do not review a stale branch tip.
Read-only review: do not edit, commit, push, or merge.

Review the diff against `docs/IMPLEMENTATION_PLAN.md` and the privacy contract.
Focus on whether both independent SDK telemetry mechanisms are actually
disabled, the request/auth flow remains intact, the inherited environment
filter is correct across supported platforms, and tests cover the behavior.
Report only concrete, evidence-backed correctness or design findings, with
file/line references. Do not use Opus for this review.
