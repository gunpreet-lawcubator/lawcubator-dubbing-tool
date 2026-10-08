"""Self-update from GitHub Releases. Only active in an installed copy
(run.ps1 sets LAWCUBATOR_MANAGED=1), never in a dev checkout."""
import io
import json
import os
import shutil
import threading
import time
import urllib.request
import zipfile

GITHUB_REPO = "gunpreet-lawcubator/lawcubator-dubbing-tool"
RESTART_EXIT_CODE = 42  # run.ps1 relaunches the app on this code

INSTALL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# Never overwritten by an update (the user's own data); created only if absent.
_KEEP_IF_EXISTS = ("backend/voices.json", "input/")

_cache: dict = {"at": 0.0, "release": None}


def managed() -> bool:
    return os.environ.get("LAWCUBATOR_MANAGED") == "1"


def current_version() -> str:
    try:
        with open(os.path.join(INSTALL_DIR, "VERSION"), encoding="utf-8") as f:
            return f.read().strip()
    except OSError:
        return "0.0.0"


def _version_tuple(v: str) -> tuple:
    return tuple(int(p) for p in v.lstrip("v").split(".") if p.isdigit())


def _latest_release() -> dict | None:
    if time.time() - _cache["at"] < 600:
        return _cache["release"]
    release = None
    try:
        req = urllib.request.Request(
            f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest",
            headers={"Accept": "application/vnd.github+json", "User-Agent": "lawcubator-dubbing-tool"},
        )
        with urllib.request.urlopen(req, timeout=8) as r:
            release = json.load(r)
    except Exception:
        release = None  # offline / rate-limited: just report "no update"
    _cache.update(at=time.time(), release=release)
    return release


def _zip_url(release: dict) -> str | None:
    for asset in release.get("assets", []):
        if asset["name"].endswith(".zip"):
            return asset["browser_download_url"]
    return None


def check() -> dict:
    current = current_version()
    info = {"current": current, "update_available": False, "latest": current, "notes": "", "enabled": managed()}
    release = _latest_release() if managed() else None
    if release and _zip_url(release):
        latest = release["tag_name"].lstrip("v")
        info.update(
            latest=latest,
            notes=release.get("body") or "",
            update_available=_version_tuple(latest) > _version_tuple(current),
        )
    return info


def _extract(zf: zipfile.ZipFile) -> None:
    root = os.path.realpath(INSTALL_DIR)
    for member in zf.infolist():
        if member.is_dir():
            continue
        name = member.filename
        dest = os.path.realpath(os.path.join(root, name))
        if not dest.startswith(root + os.sep):
            raise RuntimeError(f"Unsafe path in update: {name}")
        if os.path.exists(dest) and name.startswith(_KEEP_IF_EXISTS):
            continue
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        with zf.open(member) as src, open(dest, "wb") as out:
            shutil.copyfileobj(src, out)


def apply_update() -> str:
    """Downloads the latest release over the install and schedules a restart.
    Returns the new version. Raises on any failure before touching files."""
    info = check()
    if not info["enabled"]:
        raise RuntimeError("Updates are only available in the installed app")
    if not info["update_available"]:
        raise RuntimeError("Already up to date")
    url = _zip_url(_latest_release())
    with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "lawcubator-dubbing-tool"}), timeout=120) as r:
        data = r.read()
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        if "VERSION" not in zf.namelist():
            raise RuntimeError("Downloaded update looks invalid")
        shutil.rmtree(os.path.join(INSTALL_DIR, "frontend", "dist"), ignore_errors=True)
        _extract(zf)
    threading.Timer(1.5, lambda: os._exit(RESTART_EXIT_CODE)).start()
    return info["latest"]
