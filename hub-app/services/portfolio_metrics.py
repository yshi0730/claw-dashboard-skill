"""Pure-function portfolio metrics for the trading-desk dashboards.

No API, no DB, no numpy — stdlib only, so this is trivially unit-testable
with synthetic series and adds zero deps to the hub-app.

Inputs are exactly what AlpacaClient already returns:
  - equity curve / timestamps  ← get_portfolio_history()
  - positions                  ← positions_normalized()
  - SPY bar closes             ← get_bars("SPY")

Every function is crash-proof: degenerate input (empty, single point,
zero variance) returns a sensible 0.0 rather than raising, because a
dashboard must never 500 on a fresh account.
"""

from __future__ import annotations

import statistics
from datetime import datetime, timezone
from typing import Optional, Sequence

TRADING_DAYS = 252


# ── series helpers ─────────────────────────────────────────────────

def returns_from_equity(equity: Sequence[float]) -> list[float]:
    """Simple period returns r_i = (E_i - E_{i-1}) / E_{i-1}.

    Skips any step where the prior value is 0 (Alpaca pads leading
    points with 0 before the account is funded)."""
    out: list[float] = []
    for prev, cur in zip(equity, equity[1:]):
        if prev:
            out.append((cur - prev) / prev)
    return out


def returns_from_closes(closes: Sequence[float]) -> list[float]:
    """Same, for a benchmark close series (SPY)."""
    return returns_from_equity(closes)


# ── risk / return ratios ───────────────────────────────────────────

def sharpe_ratio(
    returns: Sequence[float], rf: float = 0.0, periods: int = TRADING_DAYS
) -> float:
    """Annualized Sharpe. rf is an *annual* risk-free rate."""
    if len(returns) < 2:
        return 0.0
    per_period_rf = rf / periods
    excess = [r - per_period_rf for r in returns]
    mu = statistics.mean(excess)
    sd = statistics.stdev(excess)  # sample std (ddof=1)
    if sd == 0:
        return 0.0
    return (mu / sd) * (periods ** 0.5)


def sortino_ratio(
    returns: Sequence[float], rf: float = 0.0, periods: int = TRADING_DAYS
) -> float:
    """Annualized Sortino — penalizes only downside deviation vs rf."""
    if len(returns) < 2:
        return 0.0
    per_period_rf = rf / periods
    excess = [r - per_period_rf for r in returns]
    mu = statistics.mean(excess)
    downside = [min(0.0, e) ** 2 for e in excess]
    dd = (sum(downside) / len(downside)) ** 0.5
    if dd == 0:
        return 0.0
    return (mu / dd) * (periods ** 0.5)


def max_drawdown(equity: Sequence[float]) -> tuple[float, int, int]:
    """Worst peak-to-trough decline.

    Returns (mdd_pct, peak_idx, trough_idx) where mdd_pct is a NEGATIVE
    percent (e.g. -24.8 means -24.8%). Monotonic-up curve → 0.0."""
    if len(equity) < 2:
        return 0.0, 0, 0
    peak = equity[0]
    peak_idx = 0
    mdd = 0.0
    mdd_peak_idx = 0
    mdd_trough_idx = 0
    for i, v in enumerate(equity):
        if v > peak:
            peak = v
            peak_idx = i
        if peak:
            dd = (v - peak) / peak
            if dd < mdd:
                mdd = dd
                mdd_peak_idx = peak_idx
                mdd_trough_idx = i
    return mdd * 100.0, mdd_peak_idx, mdd_trough_idx


def beta(
    portfolio_returns: Sequence[float], benchmark_returns: Sequence[float]
) -> float:
    """cov(p, b) / var(b) over the aligned tail of both series.

    portfolio == benchmark → 1.0. portfolio == 2*benchmark → 2.0.
    Undefined (no benchmark variance) → 0.0."""
    n = min(len(portfolio_returns), len(benchmark_returns))
    if n < 2:
        return 0.0
    p = list(portfolio_returns[-n:])
    b = list(benchmark_returns[-n:])
    pm = statistics.mean(p)
    bm = statistics.mean(b)
    cov = sum((pi - pm) * (bi - bm) for pi, bi in zip(p, b)) / (n - 1)
    var_b = sum((bi - bm) ** 2 for bi in b) / (n - 1)
    if var_b == 0:
        return 0.0
    return cov / var_b


# ── VaR ────────────────────────────────────────────────────────────

def _percentile(sorted_vals: list[float], q: float) -> float:
    """q in [0,100], linear-interpolation percentile (numpy 'linear')."""
    if not sorted_vals:
        return 0.0
    if len(sorted_vals) == 1:
        return sorted_vals[0]
    rank = (q / 100.0) * (len(sorted_vals) - 1)
    lo = int(rank)
    hi = min(lo + 1, len(sorted_vals) - 1)
    frac = rank - lo
    return sorted_vals[lo] + (sorted_vals[hi] - sorted_vals[lo]) * frac


def value_at_risk(
    equity: float,
    returns: Sequence[float],
    conf: float = 0.95,
    horizon: int = 1,
) -> float:
    """Historical-simulation VaR as a POSITIVE dollar loss magnitude.

    The (1-conf) percentile of the return distribution applied to the
    current equity, scaled by sqrt(horizon). All-gains history → ~0."""
    if not returns or equity <= 0:
        return 0.0
    s = sorted(returns)
    q = (1.0 - conf) * 100.0
    pctl = _percentile(s, q)
    if pctl >= 0:
        return 0.0
    return abs(pctl) * equity * (horizon ** 0.5)


# ── exposure / concentration ───────────────────────────────────────

def concentration(positions: Sequence[dict]) -> tuple[float, Optional[str]]:
    """Largest single position as % of gross exposure.

    Uses abs(market_value) so shorts count. Returns (top_pct, symbol)."""
    if not positions:
        return 0.0, None
    gross = sum(abs(p.get("market_value", 0.0)) for p in positions)
    if gross == 0:
        return 0.0, None
    top = max(positions, key=lambda p: abs(p.get("market_value", 0.0)))
    top_pct = abs(top.get("market_value", 0.0)) / gross * 100.0
    return top_pct, top.get("symbol")


def net_exposure(positions: Sequence[dict], equity: float) -> float:
    """Sum of position market values / equity, as a percent."""
    if equity <= 0:
        return 0.0
    net = sum(p.get("market_value", 0.0) for p in positions)
    return net / equity * 100.0


# ── period returns ─────────────────────────────────────────────────

def total_return(equity: Sequence[float]) -> float:
    """First→last percent over the whole series."""
    pts = [e for e in equity if e]
    if len(pts) < 2 or pts[0] == 0:
        return 0.0
    return (pts[-1] - pts[0]) / pts[0] * 100.0


def ytd_return(
    equity: Sequence[float], timestamps: Sequence[int]
) -> float:
    """Percent from the last point of the previous year (or first
    available point) to the latest. timestamps are unix epoch seconds
    (Alpaca portfolio-history convention)."""
    if len(equity) < 2 or len(timestamps) != len(equity):
        return total_return(equity)
    year = datetime.now(timezone.utc).year
    base_idx = 0
    for i, ts in enumerate(timestamps):
        if datetime.fromtimestamp(ts, timezone.utc).year >= year:
            base_idx = max(0, i - 1)
            break
    else:
        return total_return(equity)
    base = equity[base_idx]
    last = equity[-1]
    if not base:
        # fall back to first non-zero point
        for e in equity:
            if e:
                base = e
                break
    if not base:
        return 0.0
    return (last - base) / base * 100.0


# ── one-shot bundle for the dashboard ──────────────────────────────

def risk_cockpit(
    equity_curve: Sequence[float],
    timestamps: Sequence[int],
    bench_closes: Sequence[float],
    positions: Sequence[dict],
    current_equity: float,
    rf: float = 0.0,
) -> dict:
    """Everything the Risk Cockpit + hero Sharpe/DD need, in one call."""
    pr = returns_from_equity(equity_curve)
    br = returns_from_closes(bench_closes)
    mdd, _, _ = max_drawdown(equity_curve)
    top_pct, top_sym = concentration(positions)
    return {
        "sharpe": round(sharpe_ratio(pr, rf), 2),
        "sortino": round(sortino_ratio(pr, rf), 2),
        "max_drawdown_pct": round(mdd, 1),
        "beta": round(beta(pr, br), 2),
        "var_95_1d": round(value_at_risk(current_equity, pr, 0.95, 1), 0),
        "net_exposure_pct": round(net_exposure(positions, current_equity), 1),
        "concentration_pct": round(top_pct, 1),
        "concentration_symbol": top_sym,
        "ytd_return_pct": round(ytd_return(equity_curve, timestamps), 1),
        "total_return_pct": round(total_return(equity_curve), 1),
    }
