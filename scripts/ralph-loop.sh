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
if [[ ! -f "$prompt_file" ]]; then
    printf 'Missing prompt file: %s\n' "$prompt_file" >&2
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
upstream="$(git rev-parse --abbrev-ref --symbolic-full-name '@{u}' 2>/dev/null || true)"
if [[ "$upstream" != "origin/$branch" ]]; then
    printf 'Branch %s must track origin/%s before starting the loop.\n' "$branch" "$branch" >&2
    exit 65
fi

if [[ "$mode" == "--check" ]]; then
    printf 'Copilot CLI: %s\n' "$(copilot --version)"
    printf 'Repository: %s\n' "$root"
    printf 'Branch: %s tracking %s\n' "$branch" "$upstream"
    printf 'Prompt: %s\n' "$prompt_file"
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

iteration=1
while :; do
    status="$(ralph_status)"
    if [[ "$status" == "COMPLETE" ]]; then
        printf 'Ralph loop complete before iteration %d.\n' "$iteration"
        exit 0
    fi

    head_before="$(git rev-parse HEAD)"
    prompt="$(cat "$prompt_file")

Copilot CLI Ralph-loop iteration $iteration.
Read RALPH_PROGRESS.md if it exists. Implement exactly one coherent increment,
run its relevant checks, update progress, and create exactly one commit.
Do not push; this runner pushes after verifying the commit and clean tree.
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

    head_after="$(git rev-parse HEAD)"
    if [[ "$head_after" == "$head_before" ]]; then
        printf 'Iteration %d did not create a commit; stopping.\n' "$iteration" >&2
        exit 1
    fi
    parents="$(git rev-list --parents -n 1 "$head_after")"
    parent_count="$(printf '%s\n' "$parents" | awk '{ print NF - 1 }')"
    if [[ "$parent_count" != "1" ]] || [[ "$(git rev-parse "$head_after^")" != "$head_before" ]]; then
        printf 'Iteration %d must create exactly one direct child commit; stopping.\n' "$iteration" >&2
        exit 1
    fi
    if [[ -n "$(git status --porcelain)" ]]; then
        printf 'Iteration %d left uncommitted changes; stopping without pushing.\n' "$iteration" >&2
        exit 1
    fi

    git push origin "$branch"
    remote_head="$(git ls-remote --heads origin "$branch" | awk 'NR == 1 { print $1 }')"
    if [[ "$remote_head" != "$head_after" ]]; then
        printf 'Push verification failed for %s; stopping.\n' "$branch" >&2
        exit 1
    fi
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
