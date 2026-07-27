import json
from pathlib import Path

DEFAULT_ENTRY = {
    "status": "unavailable",
    "consecutive_errors": 0,
    "consecutive_unavailable_checks": 0,
    "stale_warned": False,
}


def load_state(state_path):
    path = Path(state_path)
    if not path.exists():
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_state(state_path, state):
    with open(state_path, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, ensure_ascii=False, sort_keys=True)
        f.write("\n")


def get_entry(state, product_id):
    return dict(state.get(product_id, DEFAULT_ENTRY))
