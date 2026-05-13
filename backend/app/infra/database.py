"""Shared SQLite setup and remaining global profile helpers.

Domain-owned tables are initialized from ``app.bootstrap.schema`` so the
infrastructure layer does not need to know product table names. This module
keeps the database path setup, WAL configuration, and legacy profile JSON
helpers used by the profile adapter.
"""

from ..core.config import get_app_config
from ..core.profile.contracts import (
    DEFAULT_PROFILE_ID,
    Goal,
    UserProfile,
)
from .jsonstore import JsonStore
from .sqlite import DB_PATH, connect

_APP_CONFIG = get_app_config()

DATA_DIR = _APP_CONFIG.data_dir

_VALID_TABLES = frozenset({"user_profile", "goals"})


# ---------------------------------------------------------------------------
# Schema & connection
# ---------------------------------------------------------------------------

def _connect():
    """Yield a sqlite3 connection with Row factory; close on exit."""
    return connect(str(DB_PATH))


def init_db() -> None:
    """Ensure the SQLite file exists and WAL mode is enabled."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with _connect() as con:
        con.execute("PRAGMA journal_mode=WAL")
        con.commit()


_STORE = JsonStore(_VALID_TABLES)


# ---------------------------------------------------------------------------
# Profile storage
# ---------------------------------------------------------------------------

def save_user_profile(profile: UserProfile) -> None:
    _STORE.save("user_profile", profile.id, profile.model_dump_json())


def load_user_profile(profile_id: str = DEFAULT_PROFILE_ID) -> UserProfile | None:
    return _STORE.load("user_profile", UserProfile, profile_id)


def save_goal(goal: Goal) -> None:
    _STORE.save("goals", goal.id, goal.model_dump_json())


def load_goals() -> list[Goal]:
    return _STORE.load_many("goals", Goal)
