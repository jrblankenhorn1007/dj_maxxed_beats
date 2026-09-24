#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "$0")/.." && pwd)"
test_root="$(mktemp -d)"
trap 'rm -rf -- "$test_root"' EXIT

main_worktree="$test_root/main"
remote="$test_root/remote.git"
fake_bin="$test_root/bin"
copilot_call_log="$test_root/copilot-calls"
gh_call_log="$test_root/gh-calls"
gh_state_dir="$test_root/gh-state"

mkdir -p "$main_worktree/scripts" "$main_worktree/docs" \
    "$fake_bin" "$test_root/home/.copilot/agents" "$gh_state_dir"
printf 'name: Ralph Loop\n' \
    > "$test_root/home/.copilot/agents/ralph-loop.agent.md"
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
- **Loop state:** No iterations have run.

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

if [[ "${1:-}" != "--agent" || "${2:-}" != "ralph-loop" ||
    "${3:-}" != "--model" || "${4:-}" != "gpt-6-luna" ]]; then
    printf 'Ralph did not select the shared agent and required gpt-6-luna model.\n' >&2
    exit 1
fi
shift 4

prompt=""
while [[ "$#" -gt 0 ]]; do
    if [[ "$1" == "--prompt" ]]; then
        shift
        prompt="${1:-}"
        break
    fi
    shift
done

branch="$(git branch --show-current)"
worktree="$(git rev-parse --show-toplevel)"
main_worktree_real="$(cd "$MAIN_WORKTREE" && pwd -P)"
if [[ "$branch" == "main" || "$worktree" == "$main_worktree_real" ]]; then
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
if ! tracking_head="$(
    git -C "$MAIN_WORKTREE" rev-parse --verify refs/remotes/origin/main 2>/dev/null
)"; then
    printf 'Copilot fixture did not receive a fetched origin/main ref.\n' >&2
    printf 'PREFLIGHT_REJECTED\n'
    exit 1
fi
if [[ "$tracking_head" != "$main_head" ]]; then
    printf 'Copilot fixture received a stale origin/main ref: %s != %s\n' \
        "$tracking_head" "$main_head" >&2
    printf 'PREFLIGHT_REJECTED\n'
    exit 1
fi
for preflight_detail in \
    "Runner-owned Git preflight (completed for this iteration)" \
    "Integration worktree: $main_worktree_real" \
    "- Branch: main" \
    "- State: clean" \
    "Local main and fetched origin/main commit: $main_head" \
    "Do not repeat the fetch or inspect the separate integration" \
    "Work only in this iteration worktree."; do
    if [[ "$prompt" != *"$preflight_detail"* ]]; then
        printf 'Copilot fixture did not receive preflight detail: %s\n' \
            "$preflight_detail" >&2
        printf 'PREFLIGHT_REJECTED\n'
        exit 1
    fi
done
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
    marker="RALPH_READY_CONTINUE"
elif [[ "$completed_iteration" == "1" ]]; then
    next_state="two mocked implementation slices."
    progress_status="COMPLETE"
    marker="RALPH_READY_COMPLETE"
elif [[ "$completed_iteration" == "2" ]]; then
    next_state="three mocked implementation slices."
    progress_status="IN_PROGRESS"
    marker="RALPH_READY_CONTINUE"
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

cat > "$fake_bin/gh" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail

if [[ "${1:-}" == "--version" ]]; then
    printf 'Mock GitHub CLI 2.0\n'
    exit 0
fi
if [[ "${1:-}" == "auth" && "${2:-}" == "status" ]]; then
    exit 0
fi
if [[ "${1:-}" != "pr" ]]; then
    printf 'Unexpected gh command: %s\n' "$*" >&2
    exit 1
fi

subcommand="$2"
shift 2
case "$subcommand" in
    create)
        head_branch=""
        while [[ "$#" -gt 0 ]]; do
            if [[ "$1" == "--head" ]]; then
                shift
                head_branch="$1"
            fi
            shift
        done
        if [[ -z "$head_branch" ]]; then
            printf 'gh pr create did not specify a head branch.\n' >&2
            exit 1
        fi
        if [[ -f "$GH_STATE_DIR/next-pr" ]]; then
            read -r pr_id < "$GH_STATE_DIR/next-pr"
        else
            pr_id=0
        fi
        pr_id=$((pr_id + 1))
        printf '%s\n' "$pr_id" > "$GH_STATE_DIR/next-pr"
        printf '%s\n' "$head_branch" > "$GH_STATE_DIR/pr-$pr_id.branch"
        printf 'create|%s\n' "$head_branch" >> "$GH_CALL_LOG"
        printf 'https://github.com/example/ralph-worktree-test/pull/%s\n' "$pr_id"
        ;;
    merge)
        pr_url="$1"
        shift
        merge_method="$1"
        if [[ "$merge_method" != "--merge" ]]; then
            printf 'gh pr merge did not use the configured merge-commit method: %s\n' \
                "$*" >&2
            exit 1
        fi
        pr_id="${pr_url##*/}"
        branch_file="$GH_STATE_DIR/pr-$pr_id.branch"
        if [[ ! -f "$branch_file" ]]; then
            printf 'Unknown pull request: %s\n' "$pr_url" >&2
            exit 1
        fi
        read -r iteration_branch < "$branch_file"
        if [[ "$pr_id" == "1" &&
            ! -f "$GH_STATE_DIR/pr-$pr_id.retry" ]]; then
            : > "$GH_STATE_DIR/pr-$pr_id.retry"
            printf 'merge-retry|%s|%s\n' "$iteration_branch" "$merge_method" \
                >> "$GH_CALL_LOG"
            printf 'Mock merge requirements are still pending.\n' >&2
            exit 1
        fi
        if [[ "${GH_MERGE_STATE:-}" == "CLOSED" ]]; then
            : > "$GH_STATE_DIR/pr-$pr_id.closed"
            printf 'merge|%s|%s\n' "$iteration_branch" "$merge_method" \
                >> "$GH_CALL_LOG"
            exit 0
        fi
        merge_repo="$GH_STATE_DIR/remote-process-$pr_id"
        git clone --quiet "$REMOTE_GIT_DIR" "$merge_repo"
        git -C "$merge_repo" config user.name "Mock Remote Merge"
        git -C "$merge_repo" config user.email "mock-remote-merge@example.invalid"
        git -C "$merge_repo" fetch --quiet origin \
            "refs/heads/$iteration_branch:refs/remotes/origin/$iteration_branch"
        if [[ "$pr_id" == "2" ]]; then
            git -C "$merge_repo" merge --squash --quiet \
                "refs/remotes/origin/$iteration_branch" >/dev/null 2>&1
            git -C "$merge_repo" commit \
                -m "Mock PR squash merge: $iteration_branch" >/dev/null
        else
            git -C "$merge_repo" merge --no-ff --no-edit \
                -m "Mock PR merge: $iteration_branch" \
                "refs/remotes/origin/$iteration_branch" >/dev/null 2>&1
        fi
        git -C "$merge_repo" push --quiet origin main
        git -C "$merge_repo" rev-parse HEAD > "$GH_STATE_DIR/pr-$pr_id.merge"
        printf 'merge|%s|%s\n' "$iteration_branch" "$merge_method" \
            >> "$GH_CALL_LOG"
        ;;
    view)
        pr_url="$1"
        shift
        pr_id="${pr_url##*/}"
        fields=""
        while [[ "$#" -gt 0 ]]; do
            if [[ "$1" == "--json" ]]; then
                shift
                fields="$1"
            fi
            shift
        done
        case "$fields" in
            state,mergedAt)
                if [[ -f "$GH_STATE_DIR/pr-$pr_id.closed" ]]; then
                    printf 'CLOSED\n'
                elif [[ -f "$GH_STATE_DIR/pr-$pr_id.merge" ]]; then
                    printf 'MERGED\n'
                else
                    printf 'OPEN\n'
                fi
                ;;
            mergeCommit)
                if [[ ! -f "$GH_STATE_DIR/pr-$pr_id.merge" ]]; then
                    printf 'The pull request has no merge commit.\n' >&2
                    exit 1
                fi
                read -r merge_commit < "$GH_STATE_DIR/pr-$pr_id.merge"
                printf '%s\n' "$merge_commit"
                ;;
            *)
                printf 'Unexpected gh pr view fields: %s\n' "$fields" >&2
                exit 1
                ;;
        esac
        ;;
    *)
        printf 'Unexpected gh pr subcommand: %s\n' "$subcommand" >&2
        exit 1
        ;;
esac
EOF
chmod +x "$fake_bin/gh"

cat > "$fake_bin/sleep" <<'EOF'
#!/usr/bin/env bash
exit 0
EOF
chmod +x "$fake_bin/sleep"

check_output="$(
    cd "$main_worktree"
    HOME="$test_root/home" \
        GH_STATE_DIR="$gh_state_dir" \
        GH_CALL_LOG="$gh_call_log" \
        REMOTE_GIT_DIR="$remote" \
        PATH="$fake_bin:/usr/bin:/bin" \
        scripts/ralph-loop.sh --check
)"
if ! printf '%s\n' "$check_output" |
    grep -Fq 'Model: GPT-6 Luna (gpt-6-luna)'; then
    printf 'FAIL: --check did not report the configured GPT-6 Luna model.\n' >&2
    exit 1
fi
if ! printf '%s\n' "$check_output" | grep -Fq 'GitHub CLI:'; then
    printf 'FAIL: --check did not verify the GitHub CLI prerequisite.\n' >&2
    exit 1
fi
if ! printf '%s\n' "$check_output" |
    grep -Fq 'Ralph Loop agent: ralph-loop'; then
    printf 'FAIL: --check did not verify the shared Ralph Loop agent.\n' >&2
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
        GH_STATE_DIR="$gh_state_dir" \
        GH_CALL_LOG="$gh_call_log" \
        REMOTE_GIT_DIR="$remote" \
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
stale_tracking_head="$(git -C "$main_worktree" rev-parse main^)"
git -C "$main_worktree" update-ref refs/remotes/origin/main "$stale_tracking_head"

if loop_output="$(
    cd "$main_worktree"
    HOME="$test_root/home" \
        MAIN_WORKTREE="$main_worktree" \
        COPILOT_CALL_LOG="$copilot_call_log" \
        GH_STATE_DIR="$gh_state_dir" \
        GH_CALL_LOG="$gh_call_log" \
        REMOTE_GIT_DIR="$remote" \
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
merge_count="$(
    git -C "$main_worktree" log --format=%s |
        awk '/^Mock PR merge: ralph\/iteration-/ { count++ }
            END { print count + 0 }'
)"
queue_squash_count="$(
    git -C "$main_worktree" log --format=%s |
        awk '/^Mock PR squash merge: ralph\/iteration-/ { count++ }
            END { print count + 0 }'
)"
if [[ "$status_report_count" != "2" || "$merge_count" != "1" ||
    "$queue_squash_count" != "1" ]]; then
    printf 'FAIL: main is missing per-iteration status or configured PR merge commits.\n' >&2
    exit 1
fi

pr_create_count="$(awk -F'|' '$1 == "create" { count++ } END { print count + 0 }' "$gh_call_log")"
pr_merge_count="$(awk -F'|' '$1 == "merge" { count++ } END { print count + 0 }' "$gh_call_log")"
if [[ "$pr_create_count" != "2" || "$pr_merge_count" != "2" ]]; then
    printf 'FAIL: each iteration must create and merge a pull request.\n' >&2
    exit 1
fi
if [[ "$(awk -F'|' '$1 == "merge-retry" { count++ }
    END { print count + 0 }' "$gh_call_log")" != "1" ]]; then
    printf 'FAIL: the runner did not retry the merge after pending requirements.\n' >&2
    exit 1
fi
if [[ "$(awk -F'|' '$1 == "merge" && $3 != "--merge" { count++ }
    END { print count + 0 }' "$gh_call_log")" != "0" ]]; then
    printf 'FAIL: the runner did not request the configured merge-commit method.\n' >&2
    exit 1
fi
if ! awk '
    /origin\/main verified/ { verified[++verified_count] = NR }
    /^RALPH_CONTINUE$/ { continued = NR }
    /^RALPH_COMPLETE$/ { completed = NR }
    END {
        if (verified_count != 2 || !(verified[1] < continued &&
            continued < verified[2] && verified[2] < completed)) {
            exit 1
        }
    }
' <<< "$loop_output"; then
    printf 'FAIL: final Ralph markers preceded their remote-main verification barriers.\n' >&2
    exit 1
fi
if printf '%s\n' "$loop_output" | grep -Eq '^RALPH_READY_(CONTINUE|COMPLETE)$'; then
    printf 'FAIL: an iteration-ready marker escaped before remote merge verification.\n' >&2
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

awk 'NR == 1 { print "Ralph-Status: IN_PROGRESS"; next } { print }' \
    "$main_worktree/docs/RALPH_PROGRESS.md" \
    > "$main_worktree/docs/RALPH_PROGRESS.md.tmp"
mv "$main_worktree/docs/RALPH_PROGRESS.md.tmp" \
    "$main_worktree/docs/RALPH_PROGRESS.md"
git -C "$main_worktree" add docs/RALPH_PROGRESS.md
git -C "$main_worktree" commit -m "test: prepare blocked merge fixture" >/dev/null
git -C "$main_worktree" push --quiet origin main

if blocked_output="$(
    cd "$main_worktree"
    HOME="$test_root/home" \
        MAIN_WORKTREE="$main_worktree" \
        COPILOT_CALL_LOG="$copilot_call_log" \
        GH_STATE_DIR="$gh_state_dir" \
        GH_CALL_LOG="$gh_call_log" \
        REMOTE_GIT_DIR="$remote" \
        GH_MERGE_STATE=CLOSED \
        PATH="$fake_bin:/usr/bin:/bin" \
        scripts/ralph-loop.sh --auto 2>&1
)"; then
    printf 'FAIL: the runner treated a closed, unmerged PR as a completed iteration.\n' >&2
    exit 1
fi
if [[ "$(printf '%s\n' "$blocked_output" | awk 'NF { last = $0 } END { print last }')" != \
    "RALPH_BLOCKED" ]]; then
    printf 'FAIL: the runner did not report the unmerged PR as blocked.\n' >&2
    printf '%s\n' "$blocked_output" >&2
    exit 1
fi
if printf '%s\n' "$blocked_output" | grep -Eq '^RALPH_(CONTINUE|COMPLETE)$'; then
    printf 'FAIL: the runner emitted a success marker for an unmerged PR.\n' >&2
    exit 1
fi
blocked_branch="$(awk -F'|' 'NR == 3 { print $2 }' "$copilot_call_log")"
blocked_worktree="$(awk -F'|' 'NR == 3 { print $3 }' "$copilot_call_log")"
if [[ ! -d "$blocked_worktree" ]] ||
    ! grep -Fq 'Ralph-Status: BLOCKED' "$blocked_worktree/docs/RALPH_PROGRESS.md" ||
    ! grep -Fq 'Remote merge blocker (iteration 3)' \
        "$blocked_worktree/docs/RALPH_PROGRESS.md"; then
    printf 'FAIL: the blocked iteration worktree/status was not preserved.\n' >&2
    exit 1
fi
blocked_local_head="$(git -C "$main_worktree" rev-parse "$blocked_branch")"
blocked_remote_head="$(
    git --git-dir="$remote" rev-parse "refs/heads/$blocked_branch"
)"
if [[ "$blocked_local_head" != "$blocked_remote_head" ]]; then
    printf 'FAIL: the blocked state was not committed and pushed to its iteration branch.\n' >&2
    printf 'Local: %s\nRemote: %s\n%s\n' \
        "$blocked_local_head" "$blocked_remote_head" "$blocked_output" >&2
    exit 1
fi
if [[ -n "$(git -C "$main_worktree" status --porcelain)" ]]; then
    printf 'FAIL: the main worktree became dirty after the blocked PR.\n' >&2
    exit 1
fi

printf 'Ralph per-iteration worktree, PR/queue merge, blocker, status, and cleanup test passed.\n'
