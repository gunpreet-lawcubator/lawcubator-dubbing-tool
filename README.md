# Lawcubator Dubbing Tool

Multi-language video dubbing (transcribe, translate, ElevenLabs voice-over, subtitles) that runs on the user's own computer.

This repository is public, but the app is password-protected and needs private API keys that are **not** in this repo. Installing requires a personal install command from Lawcubator.

## For the person installing (Windows)

Paste the install command you were sent into Command Prompt or PowerShell. It installs everything, puts a **Lawcubator Dubbing** icon on the desktop, and opens the app. Updates appear inside the app as an **Update available** button; click **Update now**.

## For the maintainer

```bash
./make-install-command.sh "password-for-the-app"   # personalised install command for a new machine
./release.sh 1.1.0 "What changed, in plain words"  # build + publish a release; installed apps offer the update
```

Local development: `backend/` is FastAPI (`uvicorn main:app`), `frontend/` is Vite/React (`npm run dev`).
