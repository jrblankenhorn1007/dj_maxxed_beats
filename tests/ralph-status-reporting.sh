#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "$0")/.." && pwd)"
test_root="$(mktemp -d)"
trap 'rm -rf -- "$test_root"' EXIT

worktree="$test_root/worktree"
remote="$test_root/remote.git"
fake_bin="$test_root/bin"

mkdir -p "$worktree/scripts" "$fake_bin" "$test_root/home"
git init --bare --initial-branch=main "$remote" >/dev/null
git init --initial-branch=main "$worktree" >/dev/null
git -C "$worktree" config user.name "Ralph Status Test"
git -C "$worktree" config user.email "ralph-status-test@example.invalid"

cp "$repo_root/scripts/ralph-loop.sh" "$worktree/scripts/ralph-loop.sh"
chmod +x "$worktree/scripts/ralph-loop.sh"
printf 'Test prompt\n' > "$worktree/RALPH_IMPLEMENTATION_PROMPT.md"
printf 'Initial project state\n' > "$worktree/README.md"
cat > "$worktree/RALPH_PROGRESS.md" <<'EOF'
Ralph-Status: IN_PROGRESS

Next task: exercise the mocked iteration.
EOF
cat > "$worktree/implementation_status.md" <<'EOF'
# Implementation Status

## Latest loop report

- **Completed implementation iteration:** `0`
- **Iteration commit:** `baseline`
- **Lines changed:** `+0 / -0`

## Current state

- Product state: pre-implementation.
EOF

git -C "$worktree" add .
git -C "$worktree" commit -m "test: seed Ralph status fixture" >/dev/null
git -C "$worktree" remote add origin https://github.com/example/ralph-status-test.git
git -C "$worktree" config \
    url."file://$remote".insteadOf https://github.com/example/ralph-status-test.git
git -C "$worktree" push --set-upstream origin main >/dev/null

cat > "$fake_bin/copilot" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail

if [[ "${1:-}" == "--version" ]]; then
    printf 'Mock Copilot CLI 1.0\n'
    exit 0
fi

completed_iteration="$(
    awk -F'`' '/^- \*\*Completed implementation iteration:\*\*/ { print $2 }' \
        implementation_status.md
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

printf 'Mock implementation change %s\n' "$((completed_iteration + 1))" >> README.md
awk -v next_state="$next_state" '
    /^- Product state:/ {
        print "- Product state: " next_state
        next
    }
    { print }
' implementation_status.md > implementation_status.md.tmp
mv implementation_status.md.tmp implementation_status.md
cat > RALPH_PROGRESS.md <<PROGRESS
Ralph-Status: $progress_status

The mocked implementation iteration completed.
PROGRESS

git add README.md implementation_status.md RALPH_PROGRESS.md
git commit -m "test: mock one implementation iteration" >/dev/null
printf '%s\n' "$marker"
EOF
chmod +x "$fake_bin/copilot"

(
    cd "$worktree"
    HOME="$test_root/home" \
        PATH="$fake_bin:/usr/bin:/bin" \
        scripts/ralph-loop.sh --auto
)

status_commit="$(git -C "$worktree" rev-parse HEAD)"
implementation_commit="$(git -C "$worktree" rev-parse HEAD^)"
short_commit="$(git -C "$worktree" rev-parse --short "$implementation_commit")"
expected_counts="$(
    git -C "$worktree" show --format= --numstat "$implementation_commit" |
        awk '$1 ~ /^[0-9]+$/ && $2 ~ /^[0-9]+$/ {
            added += $1
            deleted += $2
        }
        END { printf "+%d / -%d", added, deleted }'
)"
status_file="$worktree/implementation_status.md"
status_report_count="$(
    git -C "$worktree" log --format=%s "$status_commit" |
        awk '/^docs: update implementation status \(iteration [0-9]+\)$/ { count++ }
            END { print count + 0 }'
)"

if [[ "$(git -C "$worktree" show -s --format=%s "$status_commit")" != \
    "docs: update implementation status (iteration 2)" ]]; then
    printf 'FAIL: the runner did not create the iteration 2 status-report commit.\n' >&2
    exit 1
fi
if [[ "$status_report_count" != "2" ]]; then
    printf 'FAIL: the runner did not create a status-report commit for every iteration.\n' >&2
    exit 1
fi
if ! grep -Fq -- '- **Completed implementation iteration:** `2`' "$status_file"; then
    printf 'FAIL: the status snapshot does not report iteration 2.\n' >&2
    exit 1
fi
if [[ "$(grep -Fc -- '- **Completed implementation iteration:**' "$status_file")" != "1" ]]; then
    printf 'FAIL: the status snapshot accumulated iteration history instead of replacing it.\n' >&2
    exit 1
fi
if ! grep -Fq -- "$short_commit" "$status_file"; then
    printf 'FAIL: the status snapshot does not link the implementation commit.\n' >&2
    exit 1
fi
if ! grep -Fq -- \
    "https://github.com/example/ralph-status-test/commit/$implementation_commit" \
    "$status_file"; then
    printf 'FAIL: the implementation commit reference is not a GitHub link.\n' >&2
    exit 1
fi
if ! grep -Fq -- "- **Lines changed:** \`$expected_counts\`" "$status_file"; then
    printf 'FAIL: the status snapshot does not report the implementation LOC.\n' >&2
    exit 1
fi
if [[ "$(git --git-dir="$remote" rev-parse refs/heads/main)" != "$status_commit" ]]; then
    printf 'FAIL: the status-report commit was not pushed to origin.\n' >&2
    exit 1
fi
if [[ -n "$(git -C "$worktree" status --porcelain)" ]]; then
    printf 'FAIL: the runner left the fixture working tree dirty.\n' >&2
    exit 1
fi

printf 'Ralph status reporting test passed.\n'
