#!/bin/bash
cd "$(dirname "$0")" || exit 1

echo "MaxxedBeats Copilot setup for macOS"
echo "This installs the official GitHub Copilot CLI and a private SDK runtime."
echo "It does not ask for or store an API key."
printf "Continue? [Y/n] "
read -r answer
if [[ "$answer" =~ ^[Nn] ]]; then
    echo "Setup cancelled. You can run this file again later."
    read -r -p "Press Return to close this window."
    exit 0
fi

python=""
for name in python3.13 python3.12 python3.11; do
    if command -v "$name" >/dev/null 2>&1; then
        python="$(command -v "$name")"
        break
    fi
done

if [ -z "$python" ] && command -v brew >/dev/null 2>&1; then
    printf "Python 3.13 is needed. Install it with Homebrew? [Y/n] "
    read -r answer
    if [[ ! "$answer" =~ ^[Nn] ]]; then
        if ! brew install python@3.13; then
            echo "Homebrew could not install Python. Install Python 3.13 from https://www.python.org/downloads/macos/ and run this file again."
            read -r -p "Press Return to close this window."
            exit 1
        fi
        python="$(brew --prefix python@3.13)/bin/python3.13"
    fi
fi

if [ -z "$python" ]; then
    open "https://www.python.org/downloads/macos/" >/dev/null 2>&1 || true
    echo "Install Python 3.11 or newer from the page that opened, then double-click this file again."
    read -r -p "Press Return to close this window."
    exit 1
fi

"$python" setup_copilot.py --install-cli
result=$?
if [ "$result" -eq 0 ]; then
    echo "Done. In MaxxedBeats choose GitHub Copilot, open Keys & Privacy, and click 'Sign in to GitHub Copilot...'."
else
    echo "Setup did not finish. Follow the message above, then double-click this file again."
fi
read -r -p "Press Return to close this window."
exit "$result"
