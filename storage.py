"""
storage.py
JSON-based storage layer for the Personal AI Planner.
Every entity collection lives in its own JSON file under DATA_DIR.
Loads are lazy, saves are atomic (write to tmp file then replace).
"""
import json
import os
import uuid
from datetime import datetime

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
os.makedirs(DATA_DIR, exist_ok=True)

FILES = {
    "goals": "goals.json",
    "tasks": "tasks.json",
    "commitments": "commitments.json",
    "habits": "habits.json",
    "state": "state.json",
}

DEFAULTS = {
    "goals": [],
    "tasks": [],
    "commitments": [],
    "habits": [],
    "state": {
        "current_streak": 0,
        "best_streak": 0,
        "last_active_date": None,
    },
}


def _path(name):
    return os.path.join(DATA_DIR, FILES[name])


def load(name):
    """Load a collection from disk, creating it with defaults if missing."""
    path = _path(name)
    if not os.path.exists(path):
        save(name, DEFAULTS[name])
        return json.loads(json.dumps(DEFAULTS[name]))  # deep copy
    with open(path, "r") as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return json.loads(json.dumps(DEFAULTS[name]))


def save(name, data):
    """Atomically write a collection to disk."""
    path = _path(name)
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(data, f, indent=2, default=str)
    os.replace(tmp, path)


def new_id():
    return uuid.uuid4().hex[:10]


def now_iso():
    return datetime.now().isoformat(timespec="seconds")


def today_str():
    return datetime.now().strftime("%Y-%m-%d")
