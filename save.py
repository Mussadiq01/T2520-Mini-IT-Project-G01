import json
import os
import sys
import shutil
from pathlib import Path
from typing import Dict, Any, Optional

# Determine a persistent, user‑writable directory (handles PyInstaller onefile).
def _user_data_dir(app_name: str = "Descend") -> Path:
    # Windows: APPDATA or LOCALAPPDATA
    if os.name == "nt":
        base = os.environ.get("APPDATA") or os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Roaming")
        return Path(base) / app_name
    # macOS: ~/Library/Application Support/app_name
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / app_name
    # Linux/Unix: XDG_DATA_HOME or ~/.local/share/app_name
    xdg = os.environ.get("XDG_DATA_HOME")
    if xdg:
        return Path(xdg) / app_name
    return Path.home() / ".local" / "share" / app_name

# Legacy path (old behavior) – inside the code directory (non‑persistent for onefile)
_LEGACY_PATH = Path(__file__).parent / "save.json"

# New persistent path
_SAVE_DIR = _user_data_dir()
_SAVE_DIR.mkdir(parents=True, exist_ok=True)
SAVE_PATH = _SAVE_DIR / "save.json"   # public constant (kept)

# NEW: in‑memory staging (only written on explicit commit)
_staged_data: Dict[str, Any] = {}

def _maybe_migrate_legacy():
    """Copy legacy save.json (beside code) to new location if user has progress there and
    no new save exists yet."""
    try:
        if _LEGACY_PATH.exists() and not SAVE_PATH.exists():
            # Copy (not move) to avoid surprising user if they look in the old folder.
            shutil.copy2(_LEGACY_PATH, SAVE_PATH)
    except Exception:
        pass

_maybe_migrate_legacy()

def get_save_path() -> Path:
    """Return the resolved save file path (helper, optional)."""
    return SAVE_PATH

def save_player_data(data: dict) -> bool:
    """
    STAGED save: merge incoming data into in-memory _staged_data only.
    Disk is NOT updated until commit_player_data() is called.
    Always returns True (staging can't easily fail).
    """
    try:
        if data:
            _staged_data.update(data)
    except Exception:
        pass
    return True

def commit_player_data(extra: Optional[dict] = None) -> bool:
    """
    Keeps staged data in memory.
    """
    try:
        if SAVE_PATH.exists():
            existing = json.loads(SAVE_PATH.read_text(encoding="utf-8"))
        else:
            existing = {}
    except Exception:
        existing = {}
    merged: Dict[str, Any] = {}
    merged.update(existing)
    merged.update(_staged_data)          # staged overwrites file
    if extra:
        merged.update(extra)             # explicit extra overwrites everything
    merged.setdefault("coins", 0)
    payload = json.dumps(merged, ensure_ascii=False, indent=2)
    try:
        SAVE_PATH.write_text(payload, encoding="utf-8")
        return True
    except Exception:
        return False

def load_player_data() -> dict:
    """
    Load player data merged with any staged (unsaved) changes.
    Guarantees a dict with at least 'coins'.
    """
    try:
        if SAVE_PATH.exists():
            data = json.loads(SAVE_PATH.read_text(encoding="utf-8"))
        else:
            data = {}
    except Exception:
        data = {}
    # overlay staged (unsaved) values
    try:
        if _staged_data:
            data.update(_staged_data)
    except Exception:
        pass
    data.setdefault("coins", 0)
    return data

def has_uncommitted_changes() -> bool:
    """
    Return True if there is staged data that would change the on‑disk save.json.
    """
    if not _staged_data:
        return False
    try:
        on_disk = {}
        if SAVE_PATH.exists():
            on_disk = json.loads(SAVE_PATH.read_text(encoding="utf-8"))
    except Exception:
        on_disk = {}
    for k, v in _staged_data.items():
        if on_disk.get(k) != v:
            return True
    return False

def discard_staged_changes():
    """
    Forget any staged (unsaved) changes.
    """
    try:
        _staged_data.clear()
    except Exception:
        pass
        return False
    try:
        on_disk = {}
        if SAVE_PATH.exists():
            on_disk = json.loads(SAVE_PATH.read_text(encoding="utf-8"))
    except Exception:
        on_disk = {}
    for k, v in _staged_data.items():
        if on_disk.get(k) != v:
            return True
    return False

def discard_staged_changes():
    """
    Forget any staged (unsaved) changes.
    """
    try:
        _staged_data.clear()
    except Exception:
        pass
