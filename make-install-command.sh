#!/usr/bin/env bash
# Usage: ./make-install-command.sh "the-password-ashin-will-type"
# Builds Ashin's one-line install command (API keys + hashed password inside),
# writes it to ashin-install-command.txt (gitignored) and copies it to the clipboard.
set -euo pipefail
PASSWORD="${1:?usage: ./make-install-command.sh \"password\"}"
cd "$(dirname "$0")"
read_key() { grep -E "^$1=" backend/.env | head -1 | cut -d= -f2-; }
OR_KEY="$(read_key OPENROUTER_API_KEY)"
EL_KEY="$(read_key ELEVENLABS_API_KEY)"
HASH="$(cd backend && python3 -c 'import sys, auth; print(auth.hash_password(sys.argv[1]))' "$PASSWORD")"
URL="https://raw.githubusercontent.com/gunpreet-lawcubator/lawcubator-dubbing-tool/main/install.ps1"
CMD="powershell -NoProfile -ExecutionPolicy Bypass -Command \"& ([scriptblock]::Create((irm $URL))) -OpenRouterKey '$OR_KEY' -ElevenLabsKey '$EL_KEY' -PasswordHash '$HASH'\""
printf '%s\n' "$CMD" > ashin-install-command.txt
printf '%s' "$CMD" | pbcopy
echo "Saved to ashin-install-command.txt and copied to your clipboard. Send it to Ashin privately."
