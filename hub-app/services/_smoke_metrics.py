"""Known-answer tests for portfolio_metrics. Pure stdlib, no creds.

    python3 hub-app/services/_smoke_metrics.py

Every case has a hand-computed expected value so a regression is
obvious. Exit 0 = all pass, 1 = a failure.
"""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from services import portfolio_metrics as M  # noqa: E402

_fails = 0


def check(name: str, got, exp, tol: float = 1e-6):
    global _fails
    if isinstance(exp, (int, float)) and isinstance(got, (int, float)):
        ok = abs(got - exp) <= tol
    else:
        ok = got == exp
    mark = "✓" if ok else "✗"
    print(f"  {mark} {name}: got={got!r} expected={exp!r}")
    if not ok:
        _fails += 1


print("=== portfolio_metrics known-answer smoke ===\n")

# returns_from_equity
print("returns_from_equity")
r = M.returns_from_equity([100, 110, 99])
check("step1", r[0], 0.10)
check("step2", r[1], (99 - 110) / 110)
check("leading-zeros skipped", M.returns_from_equity([0, 0, 100, 110]), [0.10])

# max_drawdown
print("max_drawdown")
mdd, pk, tr = M.max_drawdown([100, 120, 90, 110])
check("mdd pct", mdd, -25.0)
check("peak idx", pk, 1)
check("trough idx", tr, 2)
mdd2, _, _ = M.max_drawdown([100, 110, 120, 130])
check("monotonic-up → 0", mdd2, 0.0)
check("single point → 0", M.max_drawdown([100])[0], 0.0)

# beta
print("beta")
b = [0.01, -0.02, 0.03, -0.01, 0.02]
check("p==b → 1.0", M.beta(b, b), 1.0)
check("p==2b → 2.0", M.beta([2 * x for x in b], b), 2.0)
check("too-short → 0", M.beta([0.01], [0.01]), 0.0)
check("zero-var bench → 0", M.beta([0.01, 0.02], [0.0, 0.0]), 0.0)

# concentration
print("concentration")
pos = [
    {"symbol": "A", "market_value": 50.0},
    {"symbol": "B", "market_value": 30.0},
    {"symbol": "C", "market_value": 20.0},
]
tp, ts = M.concentration(pos)
check("top pct", tp, 50.0)
check("top symbol", ts, "A")
tp2, ts2 = M.concentration(
    [{"symbol": "A", "market_value": -60.0}, {"symbol": "B", "market_value": 40.0}]
)
check("short counts (abs)", tp2, 60.0)
check("short symbol", ts2, "A")
check("empty → (0,None)", M.concentration([]), (0.0, None))

# net_exposure
print("net_exposure")
check(
    "net 100/200",
    M.net_exposure([{"market_value": 60.0}, {"market_value": 40.0}], 200.0),
    50.0,
)
check("zero equity → 0", M.net_exposure([{"market_value": 5}], 0), 0.0)

# value_at_risk
print("value_at_risk")
# sorted [-0.10,-0.05,0.0,0.05,0.10], q=5 → rank .2 → -0.10 + (.05)*.2 = -0.09
var = M.value_at_risk(1000.0, [0.10, -0.05, 0.0, 0.05, -0.10], conf=0.95)
check("hist-sim VaR $", var, 90.0, tol=1e-6)
check("all-gains → 0", M.value_at_risk(1000.0, [0.01, 0.02, 0.03]), 0.0)
check("no returns → 0", M.value_at_risk(1000.0, []), 0.0)

# sharpe / sortino (hand-computed)
print("sharpe / sortino")
# [0.02, 0.0]: mean .01, sample sd .0141421, sharpe = .7071*sqrt(252)
import math  # noqa: E402

exp_sharpe = (0.01 / math.sqrt(0.0002)) * math.sqrt(252)
check("sharpe [0.02,0.0]", M.sharpe_ratio([0.02, 0.0]), exp_sharpe, tol=1e-6)
check("sharpe mean0 → 0", M.sharpe_ratio([0.01, -0.01, 0.01, -0.01]), 0.0, tol=1e-9)
check("sharpe 1pt → 0", M.sharpe_ratio([0.01]), 0.0)
# sortino [0.02,-0.01,0.02,-0.01]: mean .005; downside mean (0+1e-4+0+1e-4)/4=5e-5
exp_sortino = (0.005 / math.sqrt(5e-5)) * math.sqrt(252)
check(
    "sortino",
    M.sortino_ratio([0.02, -0.01, 0.02, -0.01]),
    exp_sortino,
    tol=1e-6,
)

# total / ytd
print("total / ytd_return")
check("total 100→150", M.total_return([100, 120, 150]), 50.0)
yr = datetime.now(timezone.utc).year
ts_dec_prev = int(datetime(yr - 1, 12, 31, tzinfo=timezone.utc).timestamp())
ts_jan = int(datetime(yr, 1, 2, tzinfo=timezone.utc).timestamp())
ts_now = int(datetime(yr, 6, 1, tzinfo=timezone.utc).timestamp())
check(
    "ytd 100→120 = 20%",
    M.ytd_return([100, 100, 120], [ts_dec_prev, ts_jan, ts_now]),
    20.0,
)
check(
    "ytd all-this-year falls back to total",
    M.ytd_return([100, 150], [ts_jan, ts_now]),
    50.0,
)

# risk_cockpit bundle smoke (no assertion on values, just shape/no-crash)
print("risk_cockpit bundle")
rc = M.risk_cockpit(
    equity_curve=[100, 105, 102, 108, 112, 109, 115],
    timestamps=[ts_jan + i * 86400 for i in range(7)],
    bench_closes=[400, 402, 401, 404, 406, 405, 408],
    positions=pos,
    current_equity=115.0,
)
expected_keys = {
    "sharpe", "sortino", "max_drawdown_pct", "beta", "var_95_1d",
    "net_exposure_pct", "concentration_pct", "concentration_symbol",
    "ytd_return_pct", "total_return_pct",
}
check("bundle has all keys", set(rc.keys()), expected_keys)
print(f"    bundle = {rc}")

print()
if _fails:
    print(f"✗ {_fails} failure(s)")
    sys.exit(1)
print("✓ all known-answer cases pass")
