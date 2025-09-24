import json
from pathlib import Path

# Path to save file
SAVE_PATH = Path(__file__).parent / "save.json"

def save_player_data(data: dict) -> bool:
    """
    Save player data to save.json.
    Merges with existing data if the file exists.
    Returns True if successful, False otherwise.
    """
    try:
        # Load existing data if available
        if SAVE_PATH.exists():
            existing = json.loads(SAVE_PATH.read_text())
        else:
            existing = {}

        # Merge existing data with new data
        merged = {**existing, **data}

        # Save merged data back to file
        SAVE_PATH.write_text(json.dumps(merged, ensure_ascii=False, indent=2))
        return True
    except Exception:
        return False


def load_player_data() -> dict:
    """
    Load player data from save.json.
    Always ensures 'coins' key exists with default value 5000.
    Returns a dictionary.
    """
    try:
        # Load data if file exists
        if SAVE_PATH.exists():
            data = json.loads(SAVE_PATH.read_text())
        else:
            data = {}

        # Ensure default coins
        data.setdefault("coins", 5000)
        return data
    except Exception:
        # Safe default if file is missing or corrupt
        return {"coins": 5000}
