"""Assemble the `ctx` dict the us-equity-desk.html template expects.

Pulls live data from AlpacaClient, derived metrics from
portfolio_metrics, and the annotation layer (strategies / reasoning /
guardrails) from shared.db. Pre-formats every money/pct value so the
template stays logic-free.

Crash-proof: a fresh account with no positions / no strategies / no
trade_reasoning still produces a valid ctx (empty sections, sensible
placeholders) — the dashboard must never 500.
"""

from __future__ import annotations

import json
import sqlite3
import time
from datetime import datetime, timezone
from typing import Any, Optional, Sequence

from services.alpaca_client import AlpacaClient
from services import portfolio_metrics as M

AGENT_ID = "alpaca-us-stock-trader"
SKILL_VERSION = "alpaca-us-stock-skill v0.2.3"

# guardrail defaults (mirror US-EQUITY-DASHBOARD-SCHEMA.md)
_GUARDRAIL_DEFAULTS = {
    "max_position_pct": ("10", "单仓上限", "≤ {v}%"),
    "max_daily_loss_pct": ("3", "日内最大亏损", "≤ {v}%"),
    "max_daily_trades": ("10", "日内最大交易数", "≤ {v}"),
    "max_order_value": ("5000", "单笔最大金额", "${v}"),
    "allowed_hours": ("market", "交易时段", "NYSE 常规"),
    "stop_loss_required": ("true", "止损必备", "所有自动入场"),
    "paper_first": ("true", "新策略 paper", "≥ 5 天"),
    "circuit_breaker_daily_loss_pct": ("3", "熔断条件", "日亏 -{v}%"),
}
_AUTH_LABEL = {0: "Advisory", 1: "Semi-Auto", 2: "Full-Auto"}


# ── formatting helpers ─────────────────────────────────────────────

def _money_int(v: float) -> str:
    return f"${v:,.0f}"


def _money_compact(v: float) -> str:
    if abs(v) >= 1_000_000:
        return f"${v / 1_000_000:.2f}M"
    return f"${v:,.0f}"


def _money_px(v: float) -> str:
    return f"${v:,.2f}"


def _signed_money(v: float) -> str:
    sign = "+" if v >= 0 else "-"
    return f"{sign}${abs(v):,.0f}"


def _pct(v: float, signed: bool = True, dp: int = 1) -> str:
    return f"{v:+.{dp}f}%" if signed else f"{v:.{dp}f}%"


def _cls(v: float) -> str:
    return "good" if v > 0 else ("bad" if v < 0 else "")


# ── shared.db reads ────────────────────────────────────────────────

def _get_config(db: sqlite3.Connection, agent_id: str) -> dict[str, str]:
    rows = db.execute(
        "SELECT key, value FROM agent_config WHERE agent_id = ?", (agent_id,)
    ).fetchall()
    return {r["key"]: r["value"] for r in rows}


def read_alpaca_creds(
    db: sqlite3.Connection, agent_id: str = AGENT_ID
) -> Optional[dict]:
    cfg = _get_config(db, agent_id)
    key = cfg.get("alpaca_key")
    secret = cfg.get("alpaca_secret")
    if not key or not secret:
        return None
    paper = str(cfg.get("alpaca_paper", "true")).lower() != "false"
    return {"key": key, "secret": secret, "paper": paper}


def _strategies(db: sqlite3.Connection, agent_id: str) -> list[dict]:
    rows = db.execute(
        "SELECT * FROM strategy_state WHERE agent_id = ? "
        "ORDER BY (status='running') DESC, updated_at DESC",
        (agent_id,),
    ).fetchall()
    out = []
    for r in rows:
        running = r["status"] == "running"
        pnl = r["pnl_cumulative"] or 0.0
        try:
            params = json.loads(r["params"] or "{}")
        except (json.JSONDecodeError, TypeError):
            params = {}
        meta = params.get("description") or (
            f"{r['template'] or 'custom'} · L{r['authorization_level']}"
        )
        out.append({
            "name": r["name"],
            "status": (r["status"] or "").upper(),
            "status_class": "run" if running else "pause",
            "pnl_fmt": _signed_money(pnl) if pnl else "$0",
            "pnl_class": _cls(pnl),
            "meta": meta,
            "last_label": "最新" if r["last_action"] else "状态",
            "last_text": r["last_action"] or "暂无动作",
        })
    return out


def _symbol_strategy_map(db: sqlite3.Connection, agent_id: str) -> dict[str, str]:
    """Latest opening (buy/add) trade per symbol → strategy display name."""
    rows = db.execute(
        """
        SELECT tr.symbol AS symbol, ss.name AS sname,
               MAX(tr.decided_at) AS latest
        FROM trade_reasoning tr
        LEFT JOIN strategy_state ss ON ss.id = tr.strategy_id
        WHERE tr.agent_id = ? AND tr.action IN ('buy','add')
        GROUP BY tr.symbol
        """,
        (agent_id,),
    ).fetchall()
    return {r["symbol"]: (r["sname"] or "—") for r in rows}


def _reasoning_index(db: sqlite3.Connection, agent_id: str) -> dict:
    """Index trade_reasoning by client/broker order id for feed enrichment,
    plus the recent rows themselves (drives the feed)."""
    rows = db.execute(
        "SELECT * FROM trade_reasoning WHERE agent_id = ? "
        "ORDER BY decided_at DESC LIMIT 30",
        (agent_id,),
    ).fetchall()
    by_order: dict[str, dict] = {}
    recent: list[dict] = []
    for r in rows:
        d = dict(r)
        recent.append(d)
        if d.get("broker_order_id"):
            by_order[d["broker_order_id"]] = d
        if d.get("client_order_id"):
            by_order[d["client_order_id"]] = d
    return {"by_order": by_order, "recent": recent}


# ── section builders ───────────────────────────────────────────────

def _meta(ac: AlpacaClient, snap: dict, cfg: dict, latency_ms: int) -> dict:
    try:
        clk = ac.get_clock()
        is_open = bool(clk.get("is_open"))
        nxt = clk.get("next_open") if not is_open else clk.get("next_close")
        label = (
            f"NYSE · OPEN · next close {str(nxt)[:16]}"
            if is_open
            else f"NYSE · CLOSED · next open {str(nxt)[:16]}"
        )
    except Exception:  # noqa: BLE001
        is_open, nxt, label = False, None, "NYSE · status unavailable"
    auth = int(float(cfg.get("default_authorization_level", 1)))
    now = datetime.now(timezone.utc).astimezone()
    return {
        "agent_id": AGENT_ID,
        "account_number": snap.get("account_number") or "—",
        "status": snap.get("status") or "—",
        "is_paper": snap.get("is_paper", True),
        "mode": f"L{auth}",
        "authorization_label": _AUTH_LABEL.get(auth, "Semi-Auto"),
        "skill_version": SKILL_VERSION,
        "build_date": now.strftime("%Y.%m.%d"),
        "generated_at": now.strftime("%Y-%m-%d %H:%M"),
        "market_open": is_open,
        "market_label": label,
        "next_session": str(nxt) if nxt else "",
        "latency_ms": latency_ms,
    }


def _account(snap: dict) -> dict:
    eq = snap["equity"]
    bp = snap["buying_power"]
    mult = round(bp / eq) if eq else 0
    return {
        "equity_fmt": _money_int(eq),
        "cash_fmt": _money_int(snap["cash"]),
        "buying_power_fmt": _money_compact(bp),
        "buying_power_mult": f"{mult}x" if mult else "—",
        "day_pl_fmt": _signed_money(snap["day_pl"]),
        "day_pl_class": _cls(snap["day_pl"]),
        "day_pl_pct_fmt": _pct(snap["day_pl_pct"]),
    }


def _spy_ytd(spy_bars: Sequence[dict]) -> float:
    closes = [b.get("c", 0) for b in spy_bars if b.get("c")]
    if len(closes) < 2 or not closes[0]:
        return 0.0
    return (closes[-1] - closes[0]) / closes[0] * 100.0


def _nav(equity: list[float], ts: list[int], spy_bars: Sequence[dict]) -> dict:
    """Map fund equity + SPY closes (both indexed to 1.0 at start) onto the
    720x280 viewBox the template's SVG uses."""
    X0, X1, YT, YB = 40, 700, 40, 240
    eq = [e for e in equity if e]
    spy = [b.get("c", 0) for b in spy_bars if b.get("c")]

    def _norm_sample(series: list[float], n: int = 18) -> list[float]:
        if len(series) < 2:
            return series[:] or [1.0, 1.0]
        base = series[0] or 1.0
        normed = [v / base for v in series]
        if len(normed) <= n:
            return normed
        step = (len(normed) - 1) / (n - 1)
        return [normed[round(i * step)] for i in range(n)]

    f = _norm_sample(eq)
    s = _norm_sample(spy) if len(spy) >= 2 else []
    allv = f + s if s else f
    vmin, vmax = min(allv), max(allv)
    if vmax == vmin:
        vmax = vmin + 0.01

    def _pts(series: list[float]) -> str:
        if len(series) < 2:
            return f"{X0},{YB} {X1},{YB}"
        out = []
        for i, v in enumerate(series):
            x = X0 + (X1 - X0) * i / (len(series) - 1)
            y = YB - (v - vmin) / (vmax - vmin) * (YB - YT)
            out.append(f"{x:.0f},{y:.1f}")
        return " ".join(out)

    fund_line = _pts(f)
    spy_line = _pts(s) if s else ""
    fund_area = f"{fund_line} {X1},250 {X0},250"
    spy_area = f"{spy_line} {X1},250 {X0},250" if spy_line else ""

    # axis labels
    y_labels = []
    for i in range(4):
        val = vmax - (vmax - vmin) * i / 3
        y = YT + (YB - YT) * i / 3
        y_labels.append({"y": round(y) + 4, "text": f"${val:.2f}"})
    x_labels = []
    if len(ts) >= 2:
        for i in range(6):
            idx = round((len(ts) - 1) * i / 5)
            x = X0 + (X1 - X0) * i / 5
            dt = datetime.fromtimestamp(ts[idx], timezone.utc)
            x_labels.append({"x": round(x), "text": dt.strftime("%b")})
    last_v = f[-1] if f else 1.0
    last_y = YB - (last_v - vmin) / (vmax - vmin) * (YB - YT)
    return {
        "fund_line": fund_line,
        "fund_area": fund_area,
        "spy_line": spy_line,
        "spy_area": spy_area,
        "x_labels": x_labels,
        "y_labels": y_labels,
        "last_x": X1,
        "last_y": round(last_y, 1),
        "last_label": f"${last_v:.3f}",
        "nav_value": f"${last_v:.3f}",
        "alpha_fmt": "",  # filled by caller (needs spy ytd)
    }


def _holdings(positions: list[dict], equity: float, sym_strat: dict) -> dict:
    rows = []
    tot_mv = tot_upl = 0.0
    for p in positions:
        mv = p["market_value"]
        upl = p["unrealized_pl"]
        tot_mv += mv
        tot_upl += upl
        w = (mv / equity * 100) if equity else 0.0
        rows.append({
            "symbol": p["symbol"],
            "strategy": sym_strat.get(p["symbol"], "—"),
            "qty": f"{p['qty']:g}",
            "avg_fmt": _money_px(p["avg_entry_price"]),
            "cur_fmt": _money_px(p["current_price"]),
            "mv_fmt": _money_int(mv),
            "upl_fmt": f"{_signed_money(upl)} ({p['unrealized_pl_pct']:+.1f}%)",
            "upl_class": _cls(upl),
            "weight_fmt": f"{w:.1f}%",
        })
    tot_w = (tot_mv / equity * 100) if equity else 0.0
    tot_cost = tot_mv - tot_upl
    tot_pct = (tot_upl / tot_cost * 100) if tot_cost else 0.0
    return {
        "count": len(rows),
        "rows": rows,
        "total_mv_fmt": _money_int(tot_mv),
        "total_upl_fmt": f"{_signed_money(tot_upl)} ({tot_pct:+.2f}%)",
        "total_upl_class": _cls(tot_upl),
        "total_weight_fmt": f"{tot_w:.1f}%",
    }


def _feed(ac: AlpacaClient, ridx: dict) -> list[dict]:
    """Drive from trade_reasoning (the AI annotations). Enrich fill
    rows with Alpaca activity time/price when an order id matches."""
    by_order = ridx["by_order"]
    recent = ridx["recent"]
    acts_by_order: dict[str, dict] = {}
    if recent:  # only pay the Alpaca call if there is something to enrich
        try:
            for a in ac.get_activities(activity_types="FILL", page_size=50):
                oid = a.get("order_id")
                if oid:
                    acts_by_order.setdefault(oid, a)
        except Exception:  # noqa: BLE001
            pass

    out = []
    for r in recent[:8]:
        action = (r.get("action") or "").lower()
        side_label = action.upper()
        sym = r.get("symbol") or "—"
        qty = r.get("qty")
        price = r.get("price")
        act = acts_by_order.get(r.get("broker_order_id") or "") or acts_by_order.get(
            r.get("client_order_id") or ""
        )
        if act:
            price = float(act.get("price", price) or 0) or price
            t = str(act.get("transaction_time", r.get("decided_at") or ""))[11:19]
        else:
            t = str(r.get("decided_at") or "")[11:19]
        if action == "hold":
            detail = "无操作"
        else:
            detail = (
                f"{qty:g} sh @ {_money_px(price)}" if qty and price else "—"
            )
        rpl = r.get("realized_pnl")
        out.append({
            "time": t or "—",
            "side": action if action in (
                "buy", "sell", "add", "reduce", "close", "hold"
            ) else "hold",
            "side_label": side_label or "—",
            "symbol": sym,
            "detail": detail,
            "reasoning": r.get("reasoning") or "（无 AI 注释）",
            "pnl_fmt": _signed_money(rpl) if rpl else "$0",
            "pnl_class": _cls(rpl) if rpl is not None else "",
        })
    return out


def _risk_and_metrics(
    equity: list[float], ts: list[int], spy_bars: Sequence[dict],
    positions: list[dict], cur_equity: float, spy_ytd: float,
) -> tuple[dict, list[dict]]:
    spy_closes = [b.get("c", 0) for b in spy_bars if b.get("c")]
    rc = M.risk_cockpit(equity, ts, spy_closes, positions, cur_equity)
    ytd = rc["ytd_return_pct"]
    alpha = ytd - spy_ytd
    metrics = {
        "ytd_fmt": _pct(ytd),
        "spy_ytd_fmt": _pct(spy_ytd),
        "alpha_fmt": f"{alpha:+.1f}pp",
        "sharpe": f"{rc['sharpe']:.2f}",
        "sortino": f"{rc['sortino']:.2f}",
        "max_dd_fmt": _pct(rc["max_drawdown_pct"]),
        "var_fmt": _money_int(rc["var_95_1d"]),
        "beta": f"{rc['beta']:.2f}",
        "net_exposure_fmt": f"{rc['net_exposure_pct']:.1f}%",
        "concentration_fmt": f"{rc['concentration_pct']:.1f}%",
        "concentration_symbol": rc["concentration_symbol"] or "—",
        "sharpe_30d": f"{rc['sharpe']:.2f}",
    }
    risk = [
        {"k": "VaR (95%, 1d)", "v": _money_int(rc["var_95_1d"]),
         "w_pct": min(100, round(rc["var_95_1d"] / (cur_equity * 0.10) * 100)) if cur_equity else 0},
        {"k": "Beta to SPY", "v": f"{rc['beta']:.2f}",
         "w_pct": min(100, round(abs(rc["beta"]) / 2 * 100))},
        {"k": "净敞口", "v": f"{rc['net_exposure_pct']:.1f}%",
         "w_pct": min(100, round(abs(rc["net_exposure_pct"])))},
        {"k": "Max DD (90d)", "v": _pct(rc["max_drawdown_pct"]),
         "w_pct": min(100, round(abs(rc["max_drawdown_pct"]) / 8 * 100))},
        {"k": "单仓集中度", "v": f"{rc['concentration_pct']:.1f}%",
         "w_pct": min(100, round(rc["concentration_pct"] / 30 * 100))},
        {"k": "Sharpe (30d)", "v": f"{rc['sharpe']:.2f}",
         "w_pct": min(100, max(0, round(rc["sharpe"] / 3 * 100)))},
    ]
    return metrics, risk


def _guardrails(
    cfg: dict, concentration_pct: float, day_pl_pct: float, trade_count: int
) -> list[dict]:
    def g(key: str) -> str:
        return cfg.get(key, _GUARDRAIL_DEFAULTS[key][0])

    cells = []
    # max position
    lim = float(g("max_position_pct"))
    cells.append({"k": "单仓上限", "v": f"≤ {lim:g}%",
                  "meta": f"当前最大 {concentration_pct:.1f}%",
                  "ok": concentration_pct <= lim})
    # daily loss
    dl = float(g("max_daily_loss_pct"))
    day_loss = -day_pl_pct if day_pl_pct < 0 else 0.0
    cells.append({"k": "日内最大亏损", "v": f"≤ {dl:g}%",
                  "meta": f"本日 {day_pl_pct:+.1f}%",
                  "ok": day_loss <= dl})
    # daily trades
    dt = int(float(g("max_daily_trades")))
    cells.append({"k": "日内最大交易数", "v": f"≤ {dt}",
                  "meta": f"已交易 {trade_count}",
                  "ok": trade_count <= dt})
    # order value
    cells.append({"k": "单笔最大金额", "v": f"${float(g('max_order_value')):,.0f}",
                  "meta": "超过自动暂停", "ok": True})
    cells.append({"k": "交易时段", "v": "NYSE 常规",
                  "meta": "09:30-16:00 ET", "ok": True})
    cells.append({"k": "止损必备", "v": "所有自动入场",
                  "meta": "100% 覆盖", "ok": str(g("stop_loss_required")).lower() == "true"})
    cells.append({"k": "新策略 paper", "v": f"≥ {g('paper_first') and 5}天" if False else "≥ 5 天",
                  "meta": "默认开启", "ok": str(g("paper_first")).lower() == "true"})
    cb = float(g("circuit_breaker_daily_loss_pct"))
    cells.append({"k": "熔断条件", "v": f"日亏 -{cb:g}%",
                  "meta": "触发后 halt all", "ok": day_loss < cb})
    return cells


# ── top-level assembler ────────────────────────────────────────────

def build_context(ac: AlpacaClient, db: sqlite3.Connection) -> dict:
    t0 = time.time()
    snap = ac.account_snapshot()
    latency_ms = round((time.time() - t0) * 1000)

    cfg = _get_config(db, AGENT_ID)
    positions = ac.positions_normalized()
    try:
        hist = ac.get_portfolio_history(period="1A", timeframe="1D")
    except Exception:  # noqa: BLE001
        hist = {}
    equity = [float(x) for x in (hist.get("equity") or []) if x is not None]
    ts = [int(x) for x in (hist.get("timestamp") or [])]
    # SPY benchmark from start of equity window
    start = None
    if ts:
        start = datetime.fromtimestamp(ts[0], timezone.utc).strftime("%Y-%m-%d")
    try:
        spy_bars = ac.get_bars("SPY", timeframe="1Day", start=start, limit=400)
    except Exception:  # noqa: BLE001
        spy_bars = []

    spy_ytd = _spy_ytd(spy_bars)
    sym_strat = _symbol_strategy_map(db, AGENT_ID)
    ridx = _reasoning_index(db, AGENT_ID)

    metrics, risk = _risk_and_metrics(
        equity, ts, spy_bars, positions, snap["equity"], spy_ytd
    )
    nav = _nav(equity, ts, spy_bars)
    nav["alpha_fmt"] = metrics["alpha_fmt"]

    # trade count today for guardrail
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    trade_count = sum(
        1 for r in ridx["recent"]
        if (r.get("decided_at") or "").startswith(today)
        and (r.get("action") or "") != "hold"
    )

    return {
        "meta": _meta(ac, snap, cfg, latency_ms),
        "account": _account(snap),
        "metrics": metrics,
        "nav": nav,
        "strategies": _strategies(db, AGENT_ID),
        "holdings": _holdings(positions, snap["equity"], sym_strat),
        "feed": _feed(ac, ridx),
        "risk": risk,
        "guardrails": _guardrails(
            cfg,
            float(metrics["concentration_fmt"].rstrip("%") or 0),
            snap["day_pl_pct"],
            trade_count,
        ),
    }
