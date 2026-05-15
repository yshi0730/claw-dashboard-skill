"""End-to-end: real Alpaca data + seeded annotation rows → rendered page.

    ALPACA_KEY=... ALPACA_SECRET=... \
      .venv-test/bin/python hub-app/services/_smoke_e2e.py
    open /tmp/us-equity-e2e.html

Uses a throwaway temp sqlite (does NOT touch ~/.claw/shared/shared.db),
seeds agent_config with the paper creds + a couple strategy_state /
trade_reasoning rows so those panels show content, then runs the real
build_context against live Alpaca and renders the template.
"""

from __future__ import annotations

import os
import sqlite3
import sys
import tempfile
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from jinja2 import Environment, FileSystemLoader, select_autoescape  # noqa: E402
from services.alpaca_client import AlpacaClient  # noqa: E402
from services.us_equity_context import build_context, AGENT_ID  # noqa: E402

TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"
OUT = Path("/tmp/us-equity-e2e.html")

SCHEMA = """
CREATE TABLE IF NOT EXISTS strategy_state (
  id TEXT PRIMARY KEY, agent_id TEXT NOT NULL, name TEXT NOT NULL,
  template TEXT, status TEXT NOT NULL DEFAULT 'paper',
  authorization_level INTEGER DEFAULT 1, params TEXT DEFAULT '{}',
  pnl_cumulative REAL DEFAULT 0, pnl_today REAL DEFAULT 0,
  positions_count INTEGER DEFAULT 0, last_action TEXT, last_action_at TEXT,
  created_at TEXT DEFAULT (datetime('now')),
  updated_at TEXT DEFAULT (datetime('now')));
CREATE TABLE IF NOT EXISTS trade_reasoning (
  id TEXT PRIMARY KEY, agent_id TEXT NOT NULL, strategy_id TEXT,
  client_order_id TEXT, broker_order_id TEXT, action TEXT NOT NULL,
  symbol TEXT NOT NULL, qty REAL, price REAL, reasoning TEXT NOT NULL,
  realized_pnl REAL, decided_at TEXT DEFAULT (datetime('now')),
  executed_at TEXT, created_at TEXT DEFAULT (datetime('now')));
CREATE TABLE IF NOT EXISTS agent_config (
  agent_id TEXT NOT NULL, key TEXT NOT NULL, value TEXT NOT NULL,
  value_type TEXT DEFAULT 'string', category TEXT DEFAULT 'preference',
  label TEXT, updated_at TEXT DEFAULT (datetime('now')),
  PRIMARY KEY (agent_id, key));
"""


def seed(db: sqlite3.Connection, key: str, secret: str) -> None:
    db.executescript(SCHEMA)
    # creds (Option A)
    for k, v, cat in [
        ("alpaca_key", key, "mode"),
        ("alpaca_secret", secret, "mode"),
        ("alpaca_paper", "true", "mode"),
        ("default_authorization_level", "1", "mode"),
        ("max_position_pct", "10", "guardrail"),
        ("max_daily_loss_pct", "3", "guardrail"),
        ("max_daily_trades", "10", "guardrail"),
    ]:
        db.execute(
            "INSERT OR REPLACE INTO agent_config "
            "(agent_id,key,value,category) VALUES (?,?,?,?)",
            (AGENT_ID, k, v, cat),
        )
    # two strategies
    db.execute(
        "INSERT INTO strategy_state (id,agent_id,name,template,status,"
        "authorization_level,pnl_cumulative,last_action,last_action_at) "
        "VALUES (?,?,?,?,?,?,?,?,datetime('now'))",
        ("quality-mr", AGENT_ID, "Quality Mean Reversion", "quality-mr",
         "running", 1, 3120.0, "减仓 NVDA 50 @ $886.40, RSI 触及 78"),
    )
    db.execute(
        "INSERT INTO strategy_state (id,agent_id,name,template,status,"
        "authorization_level,pnl_cumulative,last_action,last_action_at) "
        "VALUES (?,?,?,?,?,?,?,?,datetime('now'))",
        ("sector-rot", AGENT_ID, "Sector Momentum Rotation", "sector-rotation",
         "paused", 1, 0.0, "市场震荡, 暂停等趋势"),
    )
    # a few reasoning rows (drive the feed; one HOLD, one with realized P&L)
    rows = [
        ("sell", "NVDA", 50, 886.40,
         "RSI 触及 78, 减仓 25%。10 日 +24% 超 2σ, 历史回撤概率 64%。", 1420.0),
        ("hold", "AAPL", None, None,
         "财报 7 天内, IV 24%→38%。守住 120 股不动, 5/21 后复评。", None),
        ("buy", "GOOGL", 100, 168.20,
         "RSI(14)=28 + 跌破 50DMA。建仓 100 股, 止损 $159.50 (-5%)。", None),
    ]
    for action, sym, qty, px, why, rpl in rows:
        db.execute(
            "INSERT INTO trade_reasoning (id,agent_id,strategy_id,action,"
            "symbol,qty,price,reasoning,realized_pnl,decided_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,datetime('now'))",
            (str(uuid.uuid4()), AGENT_ID, "quality-mr", action, sym,
             qty, px, why, rpl),
        )
    db.commit()


def main() -> int:
    key = os.environ.get("ALPACA_KEY")
    secret = os.environ.get("ALPACA_SECRET")
    if not key or not secret:
        print("set ALPACA_KEY / ALPACA_SECRET")
        return 2

    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    db = sqlite3.connect(tmp.name)
    db.row_factory = sqlite3.Row
    seed(db, key, secret)
    print(f"seeded temp db {tmp.name}")

    print("building context against LIVE Alpaca paper...")
    with AlpacaClient(key, secret, paper=True) as ac:
        ctx = build_context(ac, db)
    db.close()
    os.unlink(tmp.name)

    # spot-check a few real values came through
    print(f"  account.equity_fmt   = {ctx['account']['equity_fmt']}")
    print(f"  account.day_pl_fmt   = {ctx['account']['day_pl_fmt']}")
    print(f"  metrics.ytd_fmt      = {ctx['metrics']['ytd_fmt']}")
    print(f"  metrics.sharpe       = {ctx['metrics']['sharpe']}")
    print(f"  metrics.max_dd_fmt   = {ctx['metrics']['max_dd_fmt']}")
    print(f"  holdings.count       = {ctx['holdings']['count']}")
    print(f"  holdings rows        = "
          f"{[r['symbol'] for r in ctx['holdings']['rows']]}")
    print(f"  strategies           = "
          f"{[s['name']+'('+s['status']+')' for s in ctx['strategies']]}")
    print(f"  feed rows            = {len(ctx['feed'])} "
          f"(actions: {[e['side'] for e in ctx['feed']]})")
    print(f"  nav last_label       = {ctx['nav']['last_label']}")
    print(f"  market               = {ctx['meta']['market_label']}")

    env = Environment(
        loader=FileSystemLoader(str(TEMPLATES_DIR)),
        autoescape=select_autoescape(["html"]),
    )
    html = env.get_template("us-equity-desk.html").render(ctx=ctx)
    OUT.write_text(html, encoding="utf-8")
    assert "{{" not in html and "{%" not in html, "unrendered Jinja"
    print(f"\n✓ rendered {len(html):,} chars → {OUT}")
    print("✓ end-to-end OK (real Alpaca data + seeded annotations)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
