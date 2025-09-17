import json
import os
from pathlib import Path
from typing import Any, Dict, Optional

BASE_DIR = Path(__file__).parent
SAVE_PATH = BASE_DIR / "save.json"

def _atomic_write(path: Path, data: str) -> None:
	# Write to a temp file then replace to avoid partial writes
	tmp = path.with_suffix(path.suffix + ".tmp")
	with open(tmp, "w", encoding="utf-8") as f:
		f.write(data)
	try:
		os.replace(tmp, path)
	except Exception:
		# fallback if replace not available
		try:
			tmp.rename(path)
		except Exception:
			pass

def save_player_data(data: Dict[str, Any]) -> bool:
	"""Save player data to save.json. Returns True on success."""
	try:
		payload = json.dumps(data or {}, ensure_ascii=False, indent=2)
		_atomic_write(SAVE_PATH, payload)
		return True
	except Exception:
		return False

def load_player_data() -> Optional[Dict[str, Any]]:
	"""Load player data if present, else None."""
	try:
		if not SAVE_PATH.exists():
			return None
		with open(SAVE_PATH, "r", encoding="utf-8") as f:
			return json.load(f)
	except Exception:
		return None
