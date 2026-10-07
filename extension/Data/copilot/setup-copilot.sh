#!/usr/bin/env bash
cd "$(dirname "$0")" || exit 1
if [[ ! -t 0 ]]; then
    echo "Copilot setup needs an interactive Terminal window for confirmation and password prompts."
    echo "In your file manager, choose 'Run in Terminal' for setup-copilot.sh, then try again."
    exit 1
fi
trap 'read -r -p "Press Return to close this window."' EXIT

echo "MaxxedBeats Copilot setup for Linux"
echo "This installs the pinned, checksum-verified GitHub Copilot CLI and a private SDK runtime."
echo "It does not ask for or store an API key."
printf "Continue? [Y/n] "
read -r answer
if [[ "$answer" =~ ^[Nn] ]]; then
    echo "Setup cancelled. You can run this file again later."
    exit 0
fi

find_python() {
    for name in python3.13 python3.12 python3.11 python3; do
        if command -v "$name" >/dev/null 2>&1; then
            version="$("$name" -c 'import sys; print("%d.%d" % sys.version_info[:2])' 2>/dev/null)" || continue
            major="${version%%.*}"
            minor="${version#*.}"
            if [ "$major" -gt 3 ] || { [ "$major" -eq 3 ] && [ "$minor" -ge 11 ]; }; then
                command -v "$name"
                return 0
            fi
        fi
    done
    return 1
}

python="$(find_python || true)"
if [ -z "$python" ]; then
    echo "Python 3.11 or newer is needed. The next step may ask for your computer password."
    printf "Install Python 3.11 using your system package manager? [y/N] "
    read -r answer
    if [[ ! "$answer" =~ ^[Yy] ]]; then
        echo "Open your Linux Software app, install Python 3.11 or newer, then run this file again."
        exit 1
    fi
    if command -v apt-get >/dev/null 2>&1; then
        sudo apt-get update && sudo apt-get install -y python3.11 python3.11-venv || exit 1
    elif command -v dnf >/dev/null 2>&1; then
        sudo dnf install -y python3.11 || exit 1
    elif command -v pacman >/dev/null 2>&1; then
        sudo pacman -S --needed python python-pip || exit 1
    else
        echo "This Linux distribution's package manager is not supported by the automatic setup."
        echo "Install Python 3.11 or newer with your Software app, then run this file again."
        exit 1
    fi
    python="$(find_python || true)"
fi

if [ -z "$python" ]; then
    echo "Python 3.11 or newer is still unavailable. Restart your computer after installing Python, then try again."
    exit 1
fi

"$python" setup_copilot.py --install-cli
result=$?
if [ "$result" -eq 0 ]; then
    echo "Done. In MaxxedBeats choose GitHub Copilot, open Keys & Privacy, and click 'Sign in to GitHub Copilot...'."
else
    echo "Setup did not finish. Follow the message above, then run this file again."
fi
exit "$result"
