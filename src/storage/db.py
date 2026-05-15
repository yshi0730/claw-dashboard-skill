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

        -- ── Trading-desk dashboard tables ─────────────────────────────
        -- Written by trading agents (alpaca/futu/hyperliquid/polymarket),
        -- read by the fixed per-desk dashboard templates. See
        -- US-EQUITY-DASHBOARD-SCHEMA.md for the agent write contract.

        CREATE TABLE IF NOT EXISTS strategy_state (
            id TEXT PRIMARY KEY,                       -- slug, e.g. 'mag7-momentum'
            agent_id TEXT NOT NULL,                    -- 'alpaca-us-stock-trader'
            name TEXT NOT NULL,                        -- display 'Mag7 Momentum Rotation'
            template TEXT,                             -- mag7-momentum|quality-mr|vix-spike|sector-rotation|earnings-drift|custom
            status TEXT NOT NULL DEFAULT 'paper',      -- running|paused|paper|backtesting|stopped
            authorization_level INTEGER DEFAULT 1,     -- 0 advisory / 1 semi-auto / 2 full-auto
            params TEXT DEFAULT '{}',                  -- JSON strategy params
            pnl_cumulative REAL DEFAULT 0,             -- cached running P&L (agent updates)
            pnl_today REAL DEFAULT 0,                  -- cached today's P&L
            positions_count INTEGER DEFAULT 0,         -- open positions tied to this strategy
            last_action TEXT,                          -- '减仓 NVDA 50 @ $886.40'
            last_action_at TEXT,                       -- ISO ts of last_action
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now'))
        );
        CREATE INDEX IF NOT EXISTS idx_strategy_state_agent
            ON strategy_state(agent_id, status);

        CREATE TABLE IF NOT EXISTS trade_reasoning (
            id TEXT PRIMARY KEY,                       -- uuid
            agent_id TEXT NOT NULL,
            strategy_id TEXT,                          -- -> strategy_state.id (null = manual)
            client_order_id TEXT,                      -- agent-set; primary join to broker fills
            broker_order_id TEXT,                      -- broker order id; filled after ack
            action TEXT NOT NULL,                      -- buy|sell|add|reduce|close|hold
            symbol TEXT NOT NULL,
            qty REAL,                                  -- null for hold
            price REAL,                                -- fill price, or ref price for hold
            reasoning TEXT NOT NULL,                   -- the AI explanation
            realized_pnl REAL,                         -- set on closing/reducing trades
            decided_at TEXT DEFAULT (datetime('now')), -- when AI decided
            executed_at TEXT,                          -- when filled (null for hold/pending)
            created_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (strategy_id) REFERENCES strategy_state(id)
        );
        CREATE INDEX IF NOT EXISTS idx_trade_reasoning_feed
            ON trade_reasoning(agent_id, decided_at DESC);
        CREATE INDEX IF NOT EXISTS idx_trade_reasoning_coid
            ON trade_reasoning(client_order_id);
        CREATE INDEX IF NOT EXISTS idx_trade_reasoning_boid
            ON trade_reasoning(broker_order_id);
        CREATE INDEX IF NOT EXISTS idx_trade_reasoning_sym
            ON trade_reasoning(agent_id, symbol, decided_at DESC);

        CREATE TABLE IF NOT EXISTS agent_config (
            agent_id TEXT NOT NULL,
            key TEXT NOT NULL,                         -- 'max_position_pct' etc.
            value TEXT NOT NULL,                       -- stored as string
            value_type TEXT DEFAULT 'string',          -- number|bool|string|json
            category TEXT DEFAULT 'preference',        -- guardrail|mode|preference
            label TEXT,                                -- display label '单仓上限'
            updated_at TEXT DEFAULT (datetime('now')),
            PRIMARY KEY (agent_id, key)
        );
    """)
