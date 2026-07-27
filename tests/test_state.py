import json

from restock_notifier.state import DEFAULT_ENTRY, get_entry, load_state, save_state


def test_load_state_missing_file_returns_empty_dict(tmp_path):
    state = load_state(tmp_path / "state.json")
    assert state == {}


def test_save_then_load_round_trip(tmp_path):
    state_path = tmp_path / "state.json"
    data = {"product-a": {"status": "available", "consecutive_errors": 0,
                           "consecutive_unavailable_checks": 0, "stale_warned": False}}

    save_state(state_path, data)
    loaded = load_state(state_path)

    assert loaded == data


def test_save_state_writes_readable_json(tmp_path):
    state_path = tmp_path / "state.json"
    save_state(state_path, {"a": 1})

    raw = state_path.read_text(encoding="utf-8")
    assert json.loads(raw) == {"a": 1}


def test_get_entry_returns_default_for_unknown_product():
    entry = get_entry({}, "unknown-id")
    assert entry == DEFAULT_ENTRY


def test_get_entry_does_not_mutate_default():
    state = {}
    entry = get_entry(state, "unknown-id")
    entry["status"] = "available"

    assert DEFAULT_ENTRY["status"] == "unavailable"


def test_get_entry_returns_existing_entry():
    state = {"known-id": {"status": "available", "consecutive_errors": 1,
                           "consecutive_unavailable_checks": 0, "stale_warned": True}}
    entry = get_entry(state, "known-id")
    assert entry["status"] == "available"
    assert entry["stale_warned"] is True
