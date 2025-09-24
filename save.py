import json
import os
import tempfile
from pathlib import Path
from typing import Any, Dict, Optional

BASE_DIR = Path(__file__).parent
SAVE_PATH = BASE_DIR / "save.json"


def _atomic_write(path: Path, data: str) -> None:
    # Write to a temp file then replace to avoid partial writes
    tmp_dir = path.parent
    tmp_dir.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=path.name + ".", dir=str(tmp_dir))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(data)
        os.replace(tmp_name, path)
    finally:
        try:
            if os.path.exists(tmp_name):
                os.remove(tmp_name)
        except Exception:
            pass


def save_player_data(data: Dict[str, Any]) -> bool:
    """Merge and persist player data to save.json. Returns True on success."""
    try:
        existing: Dict[str, Any] = {}
        if SAVE_PATH.exists():
            with open(SAVE_PATH, "r", encoding="utf-8") as f:
                existing = json.load(f) or {}
    except Exception:
        existing = {}
    merged = {**existing, **(data or {})}
    try:
        payload = json.dumps(merged, ensure_ascii=False, indent=2)
        _atomic_write(SAVE_PATH, payload)
        return True
    except Exception:
        return False


def load_player_data() -> Optional[Dict[str, Any]]:
    """Load player data. Always returns a dict with at least {'coins': 5000' }."""
    try:
        if not SAVE_PATH.exists():
            # fresh profile defaults
            return {"coins": 5000}
        with open(SAVE_PATH, "r", encoding="utf-8") as f:
            data = json.load(f) or {}
        if "coins" not in data:
            data["coins"] = 5000
        return data
    except Exception:
        # Provide safe defaults even if file is missing/corrupt
        return {"coins": 5000}


__all__ = ["save_player_data", "load_player_data", "SAVE_PATH"]
