#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "$0")/.." && pwd)"
test_root="$(mktemp -d)"
trap 'rm -rf -- "$test_root"' EXIT

main_worktree="$test_root/main"
remote="$test_root/remote.git"
fake_bin="$test_root/bin"
copilot_call_log="$test_root/copilot-calls"

mkdir -p "$main_worktree/scripts" "$main_worktree/docs" \
    "$fake_bin" "$test_root/home"
git init --bare --initial-branch=main "$remote" >/dev/null
git init --initial-branch=main "$main_worktree" >/dev/null
git -C "$main_worktree" config user.name "Ralph Worktree Test"
git -C "$main_worktree" config user.email "ralph-worktree-test@example.invalid"

cp "$repo_root/scripts/ralph-loop.sh" "$main_worktree/scripts/ralph-loop.sh"
chmod +x "$main_worktree/scripts/ralph-loop.sh"
printf 'Repository entry point\n' > "$main_worktree/README.md"
printf 'Test prompt\n' > "$main_worktree/docs/RALPH_IMPLEMENTATION_PROMPT.md"
printf 'Initial project state\n' > "$main_worktree/docs/README.md"
cat > "$main_worktree/docs/RALPH_PROGRESS.md" <<'EOF'
Ralph-Status: IN_PROGRESS

Next task: exercise the mocked iteration.
EOF
cat > "$main_worktree/docs/implementation_status.md" <<'EOF'
# Implementation Status

## Latest loop report

- **Completed implementation iteration:** `0`
- **Iteration commit:** `baseline`
- **Lines changed:** `+0 / -0`

## Current state

- Product state: pre-implementation.
EOF

git -C "$main_worktree" add .
git -C "$main_worktree" commit -m "test: seed Ralph main fixture" >/dev/null
git -C "$main_worktree" remote add origin https://github.com/example/ralph-worktree-test.git
git -C "$main_worktree" config \
    url."file://$remote".insteadOf https://github.com/example/ralph-worktree-test.git
git -C "$main_worktree" push --set-upstream origin main >/dev/null

cat > "$fake_bin/copilot" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail

if [[ "${1:-}" == "--version" ]]; then
    printf 'Mock Copilot CLI 1.0\n'
    exit 0
fi

if [[ "${1:-}" != "--model" || "${2:-}" != "gpt-6-luna" ]]; then
    printf 'Ralph did not select the required gpt-6-luna model.\n' >&2
    exit 1
fi

branch="$(git branch --show-current)"
worktree="$(git rev-parse --show-toplevel)"
if [[ "$branch" == "main" || "$worktree" == "$MAIN_WORKTREE" ]]; then
    printf 'Copilot was not launched in an iteration worktree.\n' >&2
    exit 1
fi
case "$branch" in
    ralph/iteration-*) ;;
    *)
        printf 'Unexpected iteration branch: %s\n' "$branch" >&2
        exit 1
        ;;
esac

main_head="$(git -C "$MAIN_WORKTREE" rev-parse main)"
remote_head="$(
    git ls-remote --heads origin refs/heads/main |
        awk 'NR == 1 { print $1 }'
)"
if [[ "$main_head" != "$remote_head" ]]; then
    printf 'Copilot started before main was pushed: %s != %s\n' \
        "$main_head" "$remote_head" >&2
    exit 1
fi
if [[ "$(git merge-base HEAD main)" != "$main_head" ]]; then
    printf 'Iteration branch was not created from the current main tip.\n' >&2
    exit 1
fi

completed_iteration="$(
    awk -F'`' '/^- \*\*Completed implementation iteration:\*\*/ { print $2 }' \
        docs/implementation_status.md
)"
if [[ "$completed_iteration" == "0" ]]; then
    next_state="one mocked implementation slice."
    progress_status="IN_PROGRESS"
    marker="RALPH_CONTINUE"
elif [[ "$completed_iteration" == "1" ]]; then
    next_state="two mocked implementation slices."
    progress_status="COMPLETE"
    marker="RALPH_COMPLETE"
else
    printf 'Unexpected mocked iteration %s.\n' "$completed_iteration" >&2
    exit 1
fi

printf '%s|%s|%s|%s\n' \
    "$((completed_iteration + 1))" "$branch" "$worktree" "$main_head" \
    >> "$COPILOT_CALL_LOG"
printf 'Mock implementation change %s\n' "$((completed_iteration + 1))" \
    >> docs/README.md
awk -v next_state="$next_state" '
    /^- Product state:/ {
        print "- Product state: " next_state
        next
    }
    { print }
' docs/implementation_status.md > docs/implementation_status.md.tmp
mv docs/implementation_status.md.tmp docs/implementation_status.md
cat > docs/RALPH_PROGRESS.md <<PROGRESS
Ralph-Status: $progress_status

The mocked implementation iteration completed.
PROGRESS

git add docs/README.md docs/implementation_status.md docs/RALPH_PROGRESS.md
git commit -m "test: mock one implementation iteration" \
    -m "Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>" \
    >/dev/null
printf '%s\n' "$marker"
EOF
chmod +x "$fake_bin/copilot"

check_output="$(
    cd "$main_worktree"
    HOME="$test_root/home" \
        PATH="$fake_bin:/usr/bin:/bin" \
        scripts/ralph-loop.sh --check
)"
if ! printf '%s\n' "$check_output" |
    grep -Fq 'Model: GPT-6 Luna (gpt-6-luna)'; then
    printf 'FAIL: --check did not report the configured GPT-6 Luna model.\n' >&2
    exit 1
fi

printf 'Local-only checkpoint\n' >> "$main_worktree/README.md"
git -C "$main_worktree" add README.md
git -C "$main_worktree" commit -m "test: create unpushed main checkpoint" >/dev/null
if unsynced_output="$(
    cd "$main_worktree"
    HOME="$test_root/home" \
        MAIN_WORKTREE="$main_worktree" \
        COPILOT_CALL_LOG="$copilot_call_log" \
        PATH="$fake_bin:/usr/bin:/bin" \
        scripts/ralph-loop.sh --auto 2>&1
)"; then
    printf 'FAIL: the runner started with a local-only main commit.\n' >&2
    exit 1
fi
if ! printf '%s\n' "$unsynced_output" |
    grep -Fq 'does not match origin/main'; then
    printf 'FAIL: the runner did not explain the unsynced-main refusal.\n' >&2
    printf '%s\n' "$unsynced_output" >&2
    exit 1
fi
if [[ -e "$copilot_call_log" ]]; then
    printf 'FAIL: Copilot ran before main was synchronized.\n' >&2
    exit 1
fi
git -C "$main_worktree" push origin main >/dev/null

if loop_output="$(
    cd "$main_worktree"
    HOME="$test_root/home" \
        MAIN_WORKTREE="$main_worktree" \
        COPILOT_CALL_LOG="$copilot_call_log" \
        PATH="$fake_bin:/usr/bin:/bin" \
        scripts/ralph-loop.sh --auto 2>&1
)"; then
    printf '%s\n' "$loop_output"
else
    printf '%s\n' "$loop_output" >&2
    exit 1
fi

main_head="$(git -C "$main_worktree" rev-parse HEAD)"
remote_main_head="$(git --git-dir="$remote" rev-parse refs/heads/main)"
if [[ "$main_head" != "$remote_main_head" ]]; then
    printf 'FAIL: local main does not match the pushed origin/main.\n' >&2
    exit 1
fi

status_file="$main_worktree/docs/implementation_status.md"
if ! grep -Fq -- '- **Completed implementation iteration:** `2`' "$status_file"; then
    printf 'FAIL: main does not contain the iteration 2 status snapshot.\n' >&2
    exit 1
fi
if [[ "$(grep -Fc -- '- **Completed implementation iteration:**' "$status_file")" != "1" ]]; then
    printf 'FAIL: the status snapshot accumulated iteration history.\n' >&2
    exit 1
fi

call_count="$(wc -l < "$copilot_call_log" | tr -d ' ')"
if [[ "$call_count" != "2" ]]; then
    printf 'FAIL: Copilot was not invoked once for each of two iterations.\n' >&2
    exit 1
fi
first_branch="$(awk -F'|' 'NR == 1 { print $2 }' "$copilot_call_log")"
second_branch="$(awk -F'|' 'NR == 2 { print $2 }' "$copilot_call_log")"
first_worktree="$(awk -F'|' 'NR == 1 { print $3 }' "$copilot_call_log")"
second_worktree="$(awk -F'|' 'NR == 2 { print $3 }' "$copilot_call_log")"
first_main_head="$(awk -F'|' 'NR == 1 { print $4 }' "$copilot_call_log")"
second_main_head="$(awk -F'|' 'NR == 2 { print $4 }' "$copilot_call_log")"
if [[ "$first_branch" == "$second_branch" ||
    "$first_worktree" == "$second_worktree" ||
    "$first_main_head" == "$second_main_head" ]]; then
    printf 'FAIL: iterations did not use fresh branches/worktrees from updated main.\n' >&2
    exit 1
fi

for iteration_branch in "$first_branch" "$second_branch"; do
    if ! git --git-dir="$remote" show-ref --verify --quiet \
        "refs/heads/$iteration_branch"; then
        printf 'FAIL: iteration branch %s was not pushed for audit.\n' \
            "$iteration_branch" >&2
        exit 1
    fi
done

status_report_count="$(
    git -C "$main_worktree" log --format=%s --all |
        awk '/^docs: update implementation status \(iteration [0-9]+\)$/ {
            count++
        }
        END { print count + 0 }'
)"
merge_count="$(git -C "$main_worktree" log --merges --format=%H | wc -l | tr -d ' ')"
if [[ "$status_report_count" != "2" || "$merge_count" != "2" ]]; then
    printf 'FAIL: main is missing per-iteration status or merge commits.\n' >&2
    exit 1
fi

remaining_worktrees="$(
    git -C "$main_worktree" worktree list --porcelain |
        awk '/^worktree / { count++ } END { print count + 0 }'
)"
remaining_local_iteration_branches="$(
    git -C "$main_worktree" branch --list 'ralph/iteration-*' |
        awk 'NF { count++ } END { print count + 0 }'
)"
if [[ "$remaining_worktrees" != "1" || "$remaining_local_iteration_branches" != "0" ]]; then
    printf 'FAIL: the runner did not clean successful iteration worktrees/branches.\n' >&2
    exit 1
fi
if [[ -n "$(git -C "$main_worktree" status --porcelain)" ]]; then
    printf 'FAIL: the runner left main dirty after its iteration merges.\n' >&2
    exit 1
fi

if ! printf '%s\n' "$loop_output" |
    grep -Fq 'origin/main verified'; then
    printf 'FAIL: the runner did not report verified main merges.\n' >&2
    exit 1
fi

printf 'Ralph per-iteration worktree, merge, status, and cleanup test passed.\n'
