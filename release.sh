#!/usr/bin/env bash
# Usage: ./release.sh 1.1.0 "What changed, in plain words"
# Builds the frontend, zips the app, and publishes it as a GitHub Release.
# Installed copies detect it and offer an update on their own.
set -euo pipefail
VERSION="${1:?usage: ./release.sh 1.1.0 \"release notes\"}"
NOTES="${2:-Improvements and fixes.}"
cd "$(dirname "$0")"
export GH_TOKEN="${GH_TOKEN:-$(gh auth token -u gunpreet-lawcubator)}"

if [ -n "$(git status --porcelain)" ]; then
  echo "Uncommitted changes. Commit them first (git add -A && git commit), then re-run." >&2
  exit 1
fi

(cd frontend && VITE_API_BASE= npm run build)

STAGE="$(mktemp -d)/pkg"
mkdir -p "$STAGE/input"
echo "$VERSION" > "$STAGE/VERSION"
rsync -a --exclude venv --exclude __pycache__ --exclude .env backend "$STAGE/"
rsync -a frontend/dist/ "$STAGE/frontend/dist/"
rsync -a input/bgm "$STAGE/input/"
rsync -a scripts "$STAGE/"
cp run.bat "$STAGE/"

ZIP="$(dirname "$STAGE")/lawcubator-dubbing-tool-v$VERSION.zip"
(cd "$STAGE" && zip -qr "$ZIP" .)

echo "$VERSION" > VERSION
git add VERSION
git commit -q -m "Release v$VERSION" || true
git push -q origin HEAD
gh release create "v$VERSION" "$ZIP" --title "v$VERSION" --notes "$NOTES"
echo "Released v$VERSION"
