"""Smoke test for AlpacaClient. Reads creds from env — never hardcode.

    ALPACA_KEY=... ALPACA_SECRET=... python3 hub-app/services/_smoke_alpaca.py

Hits every endpoint the dashboard needs and prints a readable summary so
we can eyeball that the wrapper + auth + parsing all work end to end.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from services.alpaca_client import AlpacaClient, AlpacaError  # noqa: E402


def main() -> int:
    key = os.environ.get("ALPACA_KEY")
    secret = os.environ.get("ALPACA_SECRET")
    if not key or not secret:
        print("set ALPACA_KEY and ALPACA_SECRET env vars")
        return 2

    paper = os.environ.get("ALPACA_PAPER", "1") != "0"
    print(f"=== AlpacaClient smoke ({'PAPER' if paper else 'LIVE'}) ===\n")

    try:
        with AlpacaClient(key, secret, paper=paper) as ac:
            # 1. clock
            clk = ac.get_clock()
            print(f"[clock]      is_open={clk.get('is_open')} "
                  f"next_open={clk.get('next_open')} "
                  f"next_close={clk.get('next_close')}")

            # 2. account snapshot
            snap = ac.account_snapshot()
            print(f"[account]    #{snap['account_number']} status={snap['status']} "
                  f"paper={snap['is_paper']}")
            print(f"             equity=${snap['equity']:,.2f} "
                  f"cash=${snap['cash']:,.2f} "
                  f"buying_power=${snap['buying_power']:,.2f}")
            print(f"             day P&L=${snap['day_pl']:,.2f} "
                  f"({snap['day_pl_pct']:+.2f}%) "
                  f"PDT={snap['pattern_day_trader']} "
                  f"daytrades={snap['daytrade_count']}")

            # 3. positions
            pos = ac.positions_normalized()
            print(f"[positions]  {len(pos)} open")
            for p in pos[:8]:
                print(f"             {p['symbol']:<6} qty={p['qty']:<8g} "
                      f"@${p['avg_entry_price']:<9.2f} "
                      f"mv=${p['market_value']:,.2f} "
                      f"uPL=${p['unrealized_pl']:,.2f} "
                      f"({p['unrealized_pl_pct']:+.2f}%)")
            if not pos:
                print("             (none — fresh paper account)")

            # 4. portfolio history (1 month, daily)
            hist = ac.get_portfolio_history(period="1M", timeframe="1D")
            eq = hist.get("equity", []) or []
            ts = hist.get("timestamp", []) or []
            print(f"[history]    {len(eq)} points, timeframe={hist.get('timeframe')} "
                  f"base_value={hist.get('base_value')}")
            if eq:
                print(f"             first=${eq[0]:,.2f} last=${eq[-1]:,.2f}")

            # 5. SPY bars (benchmark)
            bars = ac.get_bars("SPY", timeframe="1Day", limit=10)
            print(f"[bars SPY]   {len(bars)} daily bars")
            if bars:
                b = bars[-1]
                print(f"             latest: t={b.get('t')} "
                      f"o={b.get('o')} h={b.get('h')} "
                      f"l={b.get('l')} c={b.get('c')} v={b.get('v')}")

            # 6. activities (fills)
            acts = ac.get_activities(activity_types="FILL", page_size=10)
            print(f"[activities] {len(acts)} recent FILL")
            for a in acts[:5]:
                print(f"             {a.get('transaction_time','?')[:19]} "
                      f"{a.get('side','?'):<4} {a.get('symbol','?'):<6} "
                      f"qty={a.get('qty','?')} @ {a.get('price','?')} "
                      f"order={a.get('order_id','?')[:8]}")
            if not acts:
                print("             (none — fresh paper account)")

            # cache check: second clock call should be memoized
            t0 = __import__("time").time()
            ac.get_clock()
            print(f"\n[cache]      2nd get_clock() served in "
                  f"{(__import__('time').time()-t0)*1000:.1f}ms (memoized)")

        print("\n✓ all endpoints reachable, auth OK, parsing OK")
        return 0

    except AlpacaError as e:
        print(f"\n✗ AlpacaError: {e}")
        return 1
    except Exception as e:  # noqa: BLE001
        print(f"\n✗ {type(e).__name__}: {e}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
