"""SQLite storage for dashboard modules, widgets, and shared data."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Optional

CLAW_DIR = Path.home() / ".claw"
SHARED_DB_PATH = CLAW_DIR / "shared" / "shared.db"

_db: Optional[sqlite3.Connection] = None


def get_db() -> sqlite3.Connection:
    global _db
    if _db is None:
        SHARED_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        _db = sqlite3.connect(str(SHARED_DB_PATH))
        _db.row_factory = sqlite3.Row
        _db.execute("PRAGMA journal_mode=WAL")
        _init_tables(_db)
    return _db


def _init_tables(db: sqlite3.Connection):
    db.executescript("""
        CREATE TABLE IF NOT EXISTS dashboard_modules (
            id TEXT PRIMARY KEY,
            agent_id TEXT NOT NULL,
            name TEXT NOT NULL,
            icon TEXT DEFAULT '📊',
            config TEXT DEFAULT '{}',
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS dashboard_widgets (
            id TEXT PRIMARY KEY,
            module_id TEXT NOT NULL,
            widget_type TEXT NOT NULL,
            title TEXT NOT NULL,
            config TEXT DEFAULT '{}',
            data TEXT DEFAULT '[]',
            position INTEGER DEFAULT 0,
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (module_id) REFERENCES dashboard_modules(id)
        );
        CREATE TABLE IF NOT EXISTS dashboard_kv (
            namespace TEXT NOT NULL,
            key TEXT NOT NULL,
            value TEXT NOT NULL,
            updated_at TEXT DEFAULT (datetime('now')),
            PRIMARY KEY (namespace, key)
        );
        CREATE TABLE IF NOT EXISTS dashboard_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_type TEXT NOT NULL,
            source TEXT NOT NULL,
            data TEXT DEFAULT '{}',
            created_at TEXT DEFAULT (datetime('now'))
        );
    """)
