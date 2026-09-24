#!/usr/bin/env bash
set -euo pipefail

main_branch="main"
copilot_model="gpt-6-luna"

on_interrupt() {
    printf '\nRalph loop interrupted. Preserve and inspect the active iteration worktree before restarting.\n' >&2
    exit 130
}
trap on_interrupt INT TERM

usage() {
    printf 'Usage: %s --check | --auto\n' "$0" >&2
    printf 'Each --auto iteration uses a fresh branch/worktree and merges to main after verification.\n' >&2
}

mode="${1:-}"
if [[ "$mode" != "--check" && "$mode" != "--auto" ]]; then
    usage
    exit 64
fi

if [[ -x "$HOME/.local/node-v24.21.0/bin/node" ]]; then
    PATH="$HOME/.local/node-v24.21.0/bin:$PATH"
    export PATH
fi
if [[ -x "$HOME/.local/copilot-cli/bin/copilot" ]]; then
    PATH="$HOME/.local/copilot-cli/bin:$PATH"
    export PATH
fi
if ! command -v copilot >/dev/null 2>&1; then
    printf 'Copilot CLI is not installed or is not on PATH.\n' >&2
    exit 69
fi

root="$(git rev-parse --show-toplevel)"
cd "$root"
docs_dir="$root/docs"
prompt_file="$docs_dir/RALPH_IMPLEMENTATION_PROMPT.md"
progress_file="$docs_dir/RALPH_PROGRESS.md"
status_file="$docs_dir/implementation_status.md"
if [[ ! -f "$prompt_file" ]]; then
    printf 'Missing prompt file: %s\n' "$prompt_file" >&2
    exit 66
fi
if [[ ! -f "$progress_file" ]]; then
    printf 'Missing progress file: %s\n' "$progress_file" >&2
    exit 66
fi
if [[ ! -f "$status_file" ]]; then
    printf 'Missing status snapshot: %s\n' "$status_file" >&2
    exit 66
fi

branch="$(git branch --show-current)"
if [[ "$branch" != "$main_branch" ]]; then
    printf 'Run the Ralph loop from the %s worktree, not branch %s.\n' \
        "$main_branch" "$branch" >&2
    exit 65
fi
if ! configured_remote_url="$(git config --get remote.origin.url)"; then
    printf 'Git remote "origin" is required.\n' >&2
    exit 65
fi
if [[ -z "$configured_remote_url" ]]; then
    printf 'Git remote "origin" is required.\n' >&2
    exit 65
fi
upstream="$(git rev-parse --abbrev-ref --symbolic-full-name '@{u}' 2>/dev/null || true)"
if [[ "$upstream" != "origin/$main_branch" ]]; then
    printf 'Branch %s must track origin/%s before starting the loop.\n' \
        "$main_branch" "$main_branch" >&2
    exit 65
fi

completed_iteration() {
    awk -F'`' '
        /^- \*\*Completed implementation iteration:\*\*/ {
            count++
            value = $2
        }
        END {
            if (count != 1 || value !~ /^[0-9]+$/) {
                exit 1
            }
            print value
        }
    ' "$status_file"
}

ralph_status_at() {
    awk -F': ' '/^Ralph-Status:/ { status = $2; count++ }
        END {
            if (count != 1) exit 1
            print status
        }' "$1"
}

github_repository_url() {
    local repository_url="$1"
    local repository_path

    case "$repository_url" in
        https://github.com/*|http://github.com/*)
            repository_url="${repository_url%.git}"
            printf '%s\n' "${repository_url%/}"
            ;;
        git@github.com:*)
            repository_path="${repository_url#git@github.com:}"
            repository_path="${repository_path%.git}"
            printf 'https://github.com/%s\n' "${repository_path%/}"
            ;;
        ssh://git@github.com/*)
            repository_path="${repository_url#ssh://git@github.com/}"
            repository_path="${repository_path%.git}"
            printf 'https://github.com/%s\n' "${repository_path%/}"
            ;;
        *)
            return 1
            ;;
    esac
}

ensure_main_synced() {
    local local_head
    local remote_refs
    local remote_head

    local_head="$(git rev-parse "$main_branch")"
    if ! remote_refs="$(git ls-remote --heads origin "refs/heads/$main_branch")"; then
        printf 'Could not verify origin/%s; refusing to start or advance the Ralph loop.\n' \
            "$main_branch" >&2
        exit 69
    fi
    remote_head="$(printf '%s\n' "$remote_refs" | awk 'NR == 1 { print $1 }')"
    if [[ -z "$remote_head" ]]; then
        printf 'Remote branch origin/%s was not found.\n' "$main_branch" >&2
        exit 65
    fi
    if [[ "$local_head" != "$remote_head" ]]; then
        printf 'Local main HEAD %s does not match origin/main (%s); refusing to start or advance.\n' \
            "$local_head" "$remote_head" >&2
        printf 'Reconcile and push main before restarting the Ralph loop.\n' >&2
        exit 65
    fi
}

if ! last_completed_iteration="$(completed_iteration)"; then
    printf 'Status snapshot must contain exactly one numeric completed-iteration field.\n' >&2
    exit 65
fi

if [[ -n "$(git status --porcelain)" ]]; then
    printf 'The main worktree must be clean before the Ralph loop starts.\n' >&2
    exit 65
fi
ensure_main_synced

if [[ "$mode" == "--check" ]]; then
    printf 'Copilot CLI: %s\n' "$(copilot --version)"
    printf 'Model: GPT-6 Luna (%s)\n' "$copilot_model"
    printf 'Repository: %s\n' "$root"
    printf 'Main branch: %s tracking %s\n' "$main_branch" "$upstream"
    printf 'Remote: origin/%s verified at %s\n' \
        "$main_branch" "$(git rev-parse --short "$main_branch")"
    printf 'Prompt: %s\n' "$prompt_file"
    printf 'Status snapshot: %s\n' "$status_file"
    printf 'Last completed implementation iteration: %s\n' "$last_completed_iteration"
    exit 0
fi

worktree_parent="$(dirname "$root")/$(basename "$root").worktrees"
initial_status="$(ralph_status_at "$progress_file")"
case "$initial_status" in
    COMPLETE)
        printf 'docs/RALPH_PROGRESS.md already marks the project complete.\n'
        exit 0
        ;;
    BLOCKED)
        printf 'docs/RALPH_PROGRESS.md marks the project blocked; see its next-step notes.\n' >&2
        exit 2
        ;;
    IN_PROGRESS) ;;
    *)
        printf 'docs/RALPH_PROGRESS.md must start with a valid Ralph-Status marker.\n' >&2
        exit 65
        ;;
esac

iteration=$((last_completed_iteration + 1))
while :; do
    status="$(ralph_status_at "$progress_file")"
    case "$status" in
        COMPLETE)
            printf 'Ralph loop complete before iteration %d.\n' "$iteration"
            exit 0
            ;;
        BLOCKED)
            printf 'Ralph loop blocked before iteration %d; see docs/RALPH_PROGRESS.md.\n' \
                "$iteration" >&2
            exit 2
            ;;
        IN_PROGRESS) ;;
        *)
            printf 'docs/RALPH_PROGRESS.md has an invalid status marker.\n' >&2
            exit 65
            ;;
    esac

    ensure_main_synced
    if [[ -n "$(git status --porcelain)" ]]; then
        printf 'Main worktree became dirty before iteration %d.\n' "$iteration" >&2
        exit 65
    fi

    main_head_before="$(git rev-parse "$main_branch")"
    main_short_before="$(git rev-parse --short "$main_head_before")"
    iteration_branch="ralph/iteration-$iteration-$main_short_before"
    iteration_worktree="$worktree_parent/ralph-iteration-$iteration-$main_short_before"
    if [[ -e "$iteration_worktree" ]]; then
        printf 'Iteration worktree already exists: %s. Preserve and inspect it before restarting.\n' \
            "$iteration_worktree" >&2
        exit 65
    fi
    if git show-ref --verify --quiet "refs/heads/$iteration_branch"; then
        printf 'Iteration branch already exists: %s. Preserve and inspect it before restarting.\n' \
            "$iteration_branch" >&2
        exit 65
    fi
    if ! existing_remote_branch="$(
        git ls-remote --heads origin "refs/heads/$iteration_branch"
    )"; then
        printf 'Could not check whether origin/%s already exists.\n' \
            "$iteration_branch" >&2
        exit 69
    fi
    if [[ -n "$existing_remote_branch" ]]; then
        printf 'Remote iteration branch origin/%s already exists; refusing to overwrite it.\n' \
            "$iteration_branch" >&2
        exit 65
    fi

    mkdir -p "$worktree_parent"
    git worktree add -b "$iteration_branch" "$iteration_worktree" "$main_branch"
    head_before="$(git -C "$iteration_worktree" rev-parse HEAD)"
    prompt="$(cat "$prompt_file")

Copilot CLI Ralph-loop iteration $iteration.
Read docs/RALPH_PROGRESS.md and docs/implementation_status.md in this iteration worktree.
Implement exactly one coherent increment, run its relevant checks, update
progress, rewrite the implementation status snapshot, and create exactly one
implementation commit. Preserve the three runner-managed status fields; the
runner creates the status-only follow-up commit.
Do not push or merge. The runner pushes this iteration branch, merges it to
main, pushes and verifies origin/main, and then removes this successful
iteration worktree and local branch. Do not switch branches or alter the main
worktree.
The project-wide iteration number for this pass is $iteration.
Finish with RALPH_CONTINUE, RALPH_BLOCKED, or RALPH_COMPLETE according to the
prompt's status-marker rules."

    printf '\n=== Copilot Ralph iteration %d on %s ===\n' \
        "$iteration" "$iteration_branch"
    cli_status=0
    if output="$(
        cd "$iteration_worktree" &&
            copilot --model "$copilot_model" --allow-all-tools --silent \
                --prompt "$prompt" 2>&1
    )"; then
        :
    else
        cli_status=$?
    fi
    printf '%s\n' "$output"

    current_branch="$(git -C "$iteration_worktree" branch --show-current)"
    if [[ "$current_branch" != "$iteration_branch" ]]; then
        printf 'Copilot changed its iteration branch (%s -> %s); preserving the worktree.\n' \
            "$iteration_branch" "$current_branch" >&2
        exit 1
    fi
    implementation_head="$(git -C "$iteration_worktree" rev-parse HEAD)"
    if [[ "$implementation_head" == "$head_before" ]]; then
        printf 'Iteration %d did not create a commit; preserving the worktree.\n' \
            "$iteration" >&2
        exit 1
    fi
    parents="$(git -C "$iteration_worktree" rev-list --parents -n 1 "$implementation_head")"
    parent_count="$(printf '%s\n' "$parents" | awk '{ print NF - 1 }')"
    if [[ "$parent_count" != "1" ]] ||
        [[ "$(git -C "$iteration_worktree" rev-parse "$implementation_head^")" != "$head_before" ]]; then
        printf 'Iteration %d must create exactly one direct-child implementation commit.\n' \
            "$iteration" >&2
        exit 1
    fi
    status_change="$(git -C "$iteration_worktree" diff-tree --no-commit-id --name-only -r \
        "$head_before" "$implementation_head" -- docs/implementation_status.md)"
    if [[ "$status_change" != "docs/implementation_status.md" ]]; then
        printf 'Iteration %d did not update docs/implementation_status.md.\n' "$iteration" >&2
        exit 1
    fi
    if [[ -n "$(git -C "$iteration_worktree" status --porcelain)" ]]; then
        printf 'Iteration %d left uncommitted changes; preserving the worktree.\n' \
            "$iteration" >&2
        exit 1
    fi

    marker="$(printf '%s\n' "$output" | awk 'NF { last = $0 } END { print last }')"
    iteration_status="$(ralph_status_at "$iteration_worktree/docs/RALPH_PROGRESS.md")"
    case "$marker" in
        RALPH_CONTINUE)
            if [[ "$iteration_status" != "IN_PROGRESS" ]]; then
                printf 'RALPH_CONTINUE requires Ralph-Status: IN_PROGRESS.\n' >&2
                exit 1
            fi
            ;;
        RALPH_BLOCKED)
            if [[ "$iteration_status" != "BLOCKED" ]]; then
                printf 'RALPH_BLOCKED requires Ralph-Status: BLOCKED.\n' >&2
                exit 1
            fi
            ;;
        RALPH_COMPLETE)
            if [[ "$iteration_status" != "COMPLETE" ]]; then
                printf 'RALPH_COMPLETE requires Ralph-Status: COMPLETE.\n' >&2
                exit 1
            fi
            ;;
        *)
            printf 'Iteration must end with RALPH_CONTINUE, RALPH_BLOCKED, or RALPH_COMPLETE.\n' >&2
            exit 1
            ;;
    esac

    loc_counts="$(
        git -C "$iteration_worktree" diff-tree --no-commit-id --numstat -r \
            "$head_before" "$implementation_head" |
            awk '$1 ~ /^[0-9]+$/ && $2 ~ /^[0-9]+$/ {
                added += $1
                deleted += $2
            }
            END { printf "%d %d\n", added, deleted }'
    )"
    read -r loc_added loc_deleted <<< "$loc_counts"
    short_commit="$(git -C "$iteration_worktree" rev-parse --short "$implementation_head")"
    if repository_web_url="$(github_repository_url "$configured_remote_url")"; then
        commit_reference="[\`$short_commit\`]($repository_web_url/commit/$implementation_head)"
    else
        commit_reference="\`$implementation_head\` (origin is not a GitHub URL)"
    fi
    iteration_status_file="$iteration_worktree/docs/implementation_status.md"
    temporary_status="$(mktemp "$iteration_worktree/.implementation-status.XXXXXX")"
    if ! awk \
        -v iteration="$iteration" \
        -v commit_reference="$commit_reference" \
        -v loc_added="$loc_added" \
        -v loc_deleted="$loc_deleted" '
        /^- \*\*Completed implementation iteration:\*\*/ {
            iteration_fields++
            print "- **Completed implementation iteration:** `" iteration "`"
            next
        }
        /^- \*\*Iteration commit:\*\*/ {
            commit_fields++
            print "- **Iteration commit:** " commit_reference
            next
        }
        /^- \*\*Lines changed:\*\*/ {
            line_count_fields++
            print "- **Lines changed:** `+" loc_added " / -" loc_deleted "` (Git numstat; text files; includes documentation; binary files excluded)"
            next
        }
        { print }
        END {
            if (iteration_fields != 1 || commit_fields != 1 || line_count_fields != 1) {
                exit 1
            }
        }
    ' "$iteration_status_file" > "$temporary_status"; then
        rm -f "$temporary_status"
        printf 'Status snapshot must contain one iteration, commit, and line-count field.\n' >&2
        exit 1
    fi
    mv "$temporary_status" "$iteration_status_file"
    if ! git -C "$iteration_worktree" diff --check -- docs/implementation_status.md; then
        printf 'Generated status snapshot has whitespace errors; preserving the worktree.\n' >&2
        exit 1
    fi
    git -C "$iteration_worktree" add -- docs/implementation_status.md
    if git -C "$iteration_worktree" diff --cached --quiet -- docs/implementation_status.md; then
        printf 'Iteration %d did not produce a status-report update.\n' "$iteration" >&2
        exit 1
    fi
    git -C "$iteration_worktree" commit \
        -m "docs: update implementation status (iteration $iteration)" \
        -m "Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
    status_head="$(git -C "$iteration_worktree" rev-parse HEAD)"
    status_short_commit="$(git -C "$iteration_worktree" rev-parse --short "$status_head")"
    if [[ "$(git -C "$iteration_worktree" rev-parse "$status_head^")" != "$implementation_head" ]] ||
        [[ "$(git -C "$iteration_worktree" diff-tree --no-commit-id --name-only -r "$status_head")" != "docs/implementation_status.md" ]]; then
        printf 'Iteration %d status-report commit was not limited to the status snapshot.\n' \
            "$iteration" >&2
        exit 1
    fi
    if [[ -n "$(git -C "$iteration_worktree" status --porcelain)" ]]; then
        printf 'Iteration %d status-report commit left its worktree dirty.\n' \
            "$iteration" >&2
        exit 1
    fi

    git -C "$iteration_worktree" push origin "$iteration_branch"
    remote_branch_refs="$(git ls-remote --heads origin "refs/heads/$iteration_branch")"
    remote_branch_head="$(printf '%s\n' "$remote_branch_refs" | awk 'NR == 1 { print $1 }')"
    if [[ "$remote_branch_head" != "$status_head" ]]; then
        printf 'Push verification failed for origin/%s; preserving the worktree.\n' \
            "$iteration_branch" >&2
        exit 1
    fi

    if [[ "$(git rev-parse "$main_branch")" != "$main_head_before" ]] ||
        [[ -n "$(git status --porcelain)" ]]; then
        printf 'Main changed during iteration %d; preserving the iteration branch/worktree.\n' \
            "$iteration" >&2
        exit 1
    fi
    ensure_main_synced
    git merge --no-ff --no-edit "$iteration_branch"
    merge_head="$(git rev-parse HEAD)"
    git push origin "$main_branch"
    remote_main_refs="$(git ls-remote --heads origin "refs/heads/$main_branch")"
    remote_main_head="$(printf '%s\n' "$remote_main_refs" | awk 'NR == 1 { print $1 }')"
    if [[ "$remote_main_head" != "$merge_head" ]]; then
        printf 'Push verification failed for origin/main; preserving the iteration worktree.\n' >&2
        exit 1
    fi

    git worktree remove "$iteration_worktree"
    git branch -d "$iteration_branch"
    if [[ -n "$(git status --porcelain)" ]]; then
        printf 'Main worktree is dirty after iteration %d cleanup.\n' "$iteration" >&2
        exit 1
    fi

    merge_short_commit="$(git rev-parse --short "$merge_head")"
    printf 'Iteration %d implementation commit: %s (+%s / -%s text lines)\n' \
        "$iteration" "$short_commit" "$loc_added" "$loc_deleted"
    printf 'Iteration %d status-report commit: %s\n' "$iteration" "$status_short_commit"
    printf 'Iteration %d merge commit: %s (%s merged to main).\n' \
        "$iteration" "$merge_short_commit" "$iteration_branch"
    printf 'origin/main verified at %s; iteration worktree cleaned.\n' \
        "$(git rev-parse --short "$merge_head")"

    if [[ "$cli_status" -ne 0 ]]; then
        printf 'Copilot CLI exited with status %d after its commits were merged.\n' \
            "$cli_status" >&2
        exit "$cli_status"
    fi

    case "$marker" in
        RALPH_CONTINUE)
            iteration=$((iteration + 1))
            ;;
        RALPH_BLOCKED)
            printf 'Ralph loop blocked; see docs/RALPH_PROGRESS.md.\n'
            exit 2
            ;;
        RALPH_COMPLETE)
            printf 'Ralph loop reports completion; review its merged evidence before release.\n'
            exit 0
            ;;
    esac
done
