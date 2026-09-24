#!/usr/bin/env bash
set -euo pipefail

on_interrupt() {
    printf '\nRalph loop interrupted. Inspect the working tree before restarting.\n' >&2
    exit 130
}
trap on_interrupt INT TERM

usage() {
    printf 'Usage: %s --check | --auto\n' "$0" >&2
    printf 'The --auto loop has no iteration-count limit; stop it with Ctrl-C.\n' >&2
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
prompt_file="$root/RALPH_IMPLEMENTATION_PROMPT.md"
progress_file="$root/RALPH_PROGRESS.md"
status_file="$root/implementation_status.md"
if [[ ! -f "$prompt_file" ]]; then
    printf 'Missing prompt file: %s\n' "$prompt_file" >&2
    exit 66
fi
if [[ ! -f "$status_file" ]]; then
    printf 'Missing status snapshot: %s\n' "$status_file" >&2
    exit 66
fi

branch="$(git branch --show-current)"
if [[ -z "$branch" ]]; then
    printf 'A named project branch is required; detached HEAD is not supported.\n' >&2
    exit 65
fi
remote_url="$(git remote get-url origin 2>/dev/null || true)"
if [[ -z "$remote_url" ]]; then
    printf 'Git remote "origin" is required.\n' >&2
    exit 65
fi
configured_remote_url="$(git config --get remote.origin.url 2>/dev/null || true)"
upstream="$(git rev-parse --abbrev-ref --symbolic-full-name '@{u}' 2>/dev/null || true)"
if [[ "$upstream" != "origin/$branch" ]]; then
    printf 'Branch %s must track origin/%s before starting the loop.\n' "$branch" "$branch" >&2
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

if ! last_completed_iteration="$(completed_iteration)"; then
    printf 'Status snapshot must contain exactly one numeric completed-iteration field.\n' >&2
    exit 65
fi

if [[ "$mode" == "--check" ]]; then
    printf 'Copilot CLI: %s\n' "$(copilot --version)"
    printf 'Repository: %s\n' "$root"
    printf 'Branch: %s tracking %s\n' "$branch" "$upstream"
    printf 'Prompt: %s\n' "$prompt_file"
    printf 'Status snapshot: %s\n' "$status_file"
    printf 'Last completed implementation iteration: %s\n' "$last_completed_iteration"
    exit 0
fi

if [[ -n "$(git status --porcelain)" ]]; then
    printf 'Working tree must be clean before --auto starts.\n' >&2
    exit 65
fi

ralph_status() {
    if [[ -f "$progress_file" ]]; then
        awk -F': ' '/^Ralph-Status:/ { status = $2 } END { print status }' "$progress_file"
    fi
}

status="$(ralph_status)"
if [[ "$status" == "COMPLETE" ]]; then
    printf 'RALPH_PROGRESS.md already marks the project complete.\n'
    exit 0
fi

iteration=$((last_completed_iteration + 1))
while :; do
    status="$(ralph_status)"
    if [[ "$status" == "COMPLETE" ]]; then
        printf 'Ralph loop complete before iteration %d.\n' "$iteration"
        exit 0
    fi

    head_before="$(git rev-parse HEAD)"
    prompt="$(cat "$prompt_file")

Copilot CLI Ralph-loop iteration $iteration.
Read RALPH_PROGRESS.md and implementation_status.md. Implement exactly one
coherent increment, run its relevant checks, update progress, rewrite the
implementation_status.md snapshot (do not append history), and create exactly
one implementation commit. Preserve the status file's three runner-managed
fields; this runner finalizes their iteration number, commit link, and line
counts in a separate status-report commit.
Do not push; this runner creates and pushes the status-report commit after
verifying the implementation commit and clean tree.
The project-wide iteration number for this pass is $iteration.
Finish with RALPH_CONTINUE, RALPH_BLOCKED, or RALPH_COMPLETE according to the
prompt's status-marker rules."

    printf '\n=== Copilot Ralph iteration %d ===\n' "$iteration"
    cli_status=0
    if output="$(copilot --allow-all-tools --silent --prompt "$prompt" 2>&1)"; then
        :
    else
        cli_status=$?
    fi
    printf '%s\n' "$output"

    current_branch="$(git branch --show-current)"
    if [[ "$current_branch" != "$branch" ]]; then
        printf 'Copilot changed branches (%s -> %s); stopping without pushing.\n' "$branch" "$current_branch" >&2
        exit 1
    fi

    implementation_head="$(git rev-parse HEAD)"
    if [[ "$implementation_head" == "$head_before" ]]; then
        printf 'Iteration %d did not create a commit; stopping.\n' "$iteration" >&2
        exit 1
    fi
    parents="$(git rev-list --parents -n 1 "$implementation_head")"
    parent_count="$(printf '%s\n' "$parents" | awk '{ print NF - 1 }')"
    if [[ "$parent_count" != "1" ]] || [[ "$(git rev-parse "$implementation_head^")" != "$head_before" ]]; then
        printf 'Iteration %d must create exactly one direct-child implementation commit; stopping.\n' "$iteration" >&2
        exit 1
    fi
    status_change="$(git diff-tree --no-commit-id --name-only -r \
        "$implementation_head^" "$implementation_head" -- implementation_status.md)"
    if [[ "$status_change" != "implementation_status.md" ]]; then
        printf 'Iteration %d did not update implementation_status.md; stopping.\n' "$iteration" >&2
        exit 1
    fi
    if [[ -n "$(git status --porcelain)" ]]; then
        printf 'Iteration %d left uncommitted changes; stopping without pushing.\n' "$iteration" >&2
        exit 1
    fi

    loc_counts="$(
        git diff-tree --no-commit-id --numstat -r \
            "$implementation_head^" "$implementation_head" |
            awk '$1 ~ /^[0-9]+$/ && $2 ~ /^[0-9]+$/ {
                added += $1
                deleted += $2
            }
            END { printf "%d %d\n", added, deleted }'
    )"
    read -r loc_added loc_deleted <<< "$loc_counts"
    short_commit="$(git rev-parse --short "$implementation_head")"
    if repository_web_url="$(github_repository_url "$configured_remote_url")"; then
        commit_reference="[\`$short_commit\`]($repository_web_url/commit/$implementation_head)"
    else
        commit_reference="\`$implementation_head\` (origin is not a GitHub URL)"
    fi
    temporary_status="$(mktemp "$root/.implementation-status.XXXXXX")"
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
    ' "$status_file" > "$temporary_status"; then
        rm -f "$temporary_status"
        printf 'Status snapshot must contain one iteration, commit, and line-count field.\n' >&2
        exit 1
    fi
    mv "$temporary_status" "$status_file"
    if ! git diff --check -- "$status_file"; then
        printf 'Generated status snapshot has whitespace errors; stopping.\n' >&2
        exit 1
    fi
    git add -- "$status_file"
    if git diff --cached --quiet -- "$status_file"; then
        printf 'Iteration %d did not produce a status-report update; stopping.\n' "$iteration" >&2
        exit 1
    fi
    git commit \
        -m "docs: update implementation status (iteration $iteration)" \
        -m "Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
    status_head="$(git rev-parse HEAD)"
    if [[ "$(git rev-parse "$status_head^")" != "$implementation_head" ]] ||
        [[ "$(git diff-tree --no-commit-id --name-only -r "$status_head")" != "implementation_status.md" ]]; then
        printf 'Iteration %d status-report commit was not limited to the status snapshot; stopping.\n' "$iteration" >&2
        exit 1
    fi
    if [[ -n "$(git status --porcelain)" ]]; then
        printf 'Iteration %d status-report commit left uncommitted changes; stopping without pushing.\n' "$iteration" >&2
        exit 1
    fi

    git push origin "$branch"
    remote_head="$(git ls-remote --heads origin "$branch" | awk 'NR == 1 { print $1 }')"
    if [[ "$remote_head" != "$status_head" ]]; then
        printf 'Push verification failed for %s; stopping.\n' "$branch" >&2
        exit 1
    fi
    printf 'Iteration %d implementation commit: %s (+%s / -%s text lines)\n' \
        "$iteration" "$short_commit" "$loc_added" "$loc_deleted"
    printf 'Iteration %d status-report commit: %s\n' \
        "$iteration" "$(git rev-parse --short "$status_head")"
    if [[ "$cli_status" -ne 0 ]]; then
        printf 'Copilot CLI exited with status %d after its commit was pushed.\n' "$cli_status" >&2
        exit "$cli_status"
    fi

    marker="$(printf '%s\n' "$output" | awk 'NF { last = $0 } END { print last }')"
    status="$(ralph_status)"
    case "$marker" in
        RALPH_CONTINUE)
            if [[ "$status" != "IN_PROGRESS" ]]; then
                printf 'RALPH_CONTINUE requires Ralph-Status: IN_PROGRESS.\n' >&2
                exit 1
            fi
            ;;
        RALPH_BLOCKED)
            if [[ "$status" != "BLOCKED" ]]; then
                printf 'RALPH_BLOCKED requires Ralph-Status: BLOCKED.\n' >&2
                exit 1
            fi
            printf 'Ralph loop blocked; see RALPH_PROGRESS.md.\n'
            exit 2
            ;;
        RALPH_COMPLETE)
            if [[ "$status" != "COMPLETE" ]]; then
                printf 'RALPH_COMPLETE requires Ralph-Status: COMPLETE.\n' >&2
                exit 1
            fi
            printf 'Ralph loop reports completion; review its evidence before release.\n'
            exit 0
            ;;
        *)
            printf 'Iteration must end with RALPH_CONTINUE, RALPH_BLOCKED, or RALPH_COMPLETE.\n' >&2
            exit 1
            ;;
    esac

    iteration=$((iteration + 1))
done
