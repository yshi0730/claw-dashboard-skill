"""Render us-equity-desk.html with a mock ctx to verify layout.

    .venv-test/bin/python hub-app/services/_smoke_template.py
    open /tmp/us-equity-desk-rendered.html

Builds a representative context (mirrors the original static design so
visual regressions are obvious), renders via Jinja2, writes the HTML.
No API, no DB — pure template validation. The real ctx is assembled by
the route (#5) from AlpacaClient + portfolio_metrics + shared.db.
"""

from __future__ import annotations

from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"
OUT = Path("/tmp/us-equity-desk-rendered.html")


def mock_ctx() -> dict:
    return {
        "meta": {
            "agent_id": "alpaca-us-stock-trader",
            "account_number": "PA3WHJKDMGN0",
            "status": "ACTIVE",
            "is_paper": True,
            "mode": "L1",
            "authorization_label": "Semi-Auto",
            "skill_version": "alpaca-us-stock-skill v0.2.3",
            "build_date": "2026.05.15",
            "generated_at": "2026-05-15 22:40 北京",
            "market_open": False,
            "market_label": "NYSE · CLOSED · next open 周一 09:30 ET",
            "next_session": "2026-05-18T09:30:00-04:00",
            "latency_ms": 14,
        },
        "account": {
            "equity_fmt": "$1,800,758",
            "cash_fmt": "$312,440",
            "buying_power_fmt": "$4.18M",
            "buying_power_mult": "2x",
            "day_pl_fmt": "+$12,400",
            "day_pl_class": "good",
            "day_pl_pct_fmt": "+0.69%",
        },
        "metrics": {
            "ytd_fmt": "+24.2%",
            "spy_ytd_fmt": "+9.2%",
            "alpha_fmt": "+15.0pp",
            "sharpe": "1.92",
            "sortino": "2.61",
            "max_dd_fmt": "-4.8%",
            "var_fmt": "$22,400",
            "beta": "1.08",
            "net_exposure_fmt": "72.5%",
            "concentration_fmt": "9.1%",
            "concentration_symbol": "SPY",
            "sharpe_30d": "2.41",
        },
        "nav": {
            "spy_area": "40,218 80,212 120,210 160,202 200,200 240,194 280,188 320,182 360,176 400,168 440,162 480,158 520,150 560,144 600,138 640,132 680,128 700,126 700,250 40,250",
            "spy_line": "40,218 80,212 120,210 160,202 200,200 240,194 280,188 320,182 360,176 400,168 440,162 480,158 520,150 560,144 600,138 640,132 680,128 700,126",
            "fund_area": "40,228 80,210 120,212 160,196 200,186 240,178 280,165 320,148 360,138 400,124 440,112 480,100 520,86 560,72 600,60 640,48 680,40 700,34 700,250 40,250",
            "fund_line": "40,228 80,210 120,212 160,196 200,186 240,178 280,165 320,148 360,138 400,124 440,112 480,100 520,86 560,72 600,60 640,48 680,40 700,34",
            "x_labels": [
                {"x": 60, "text": "Jan"}, {"x": 180, "text": "Feb"},
                {"x": 300, "text": "Mar"}, {"x": 420, "text": "Apr"},
                {"x": 540, "text": "May"}, {"x": 680, "text": "15日"},
            ],
            "y_labels": [
                {"y": 64, "text": "$1.25"}, {"y": 124, "text": "$1.15"},
                {"y": 184, "text": "$1.05"}, {"y": 244, "text": "$0.95"},
            ],
            "last_x": 700, "last_y": 34, "last_label": "$1.242",
            "nav_value": "$1.242", "alpha_fmt": "+15.0pp",
        },
        "strategies": [
            {"name": "Mag7 Momentum Rotation", "status": "RUNNING", "status_class": "run",
             "pnl_fmt": "+$6,840", "pnl_class": "good",
             "meta": "7 stocks ranked weekly · top 3 equal-weight · L1 (Semi-Auto)",
             "last_label": "最新", "last_text": "持仓 NVDA / MSFT / META · 周一再平衡, 上次 5/13 09:35"},
            {"name": "Quality Mean Reversion", "status": "RUNNING", "status_class": "run",
             "pnl_fmt": "+$3,120", "pnl_class": "good",
             "meta": "10 优质股 RSI<30 买入 · RSI>50 卖出 · 止损 -5% · L1",
             "last_label": "最新", "last_text": "14:32 减仓 NVDA 50 股 @ $886.40, RSI 触及 78"},
            {"name": "VIX Spike Buyer", "status": "RUNNING", "status_class": "run",
             "pnl_fmt": "+$1,940", "pnl_class": "good",
             "meta": "VIX>25 + SPY 2 日跌 3% 触发 · 上次触发 4/22 · L1",
             "last_label": "监控中", "last_text": "VIX 14.2 (低于阈值), 暂无信号"},
            {"name": "Sector Momentum Rotation", "status": "PAUSED", "status_class": "pause",
             "pnl_fmt": "$0", "pnl_class": "",
             "meta": "9 SPDR ETF 月度排名前 2 · 已暂停, SPY 接近 50DMA 不触发",
             "last_label": "原因", "last_text": "当前市场震荡, 等待趋势明朗后重启"},
            {"name": "Earnings Drift Rider", "status": "RUNNING", "status_class": "run",
             "pnl_fmt": "+$540", "pnl_class": "good",
             "meta": "持仓股财报后超预期且 +2% → 5 日跟随 · L1",
             "last_label": "监控中", "last_text": "AAPL 财报 5/21, 提前 3 日开始密切监控"},
        ],
        "holdings": {
            "count": 8,
            "rows": [
                {"symbol": "NVDA", "strategy": "Quality MR", "qty": "50", "avg_fmt": "$842.10", "cur_fmt": "$886.40", "mv_fmt": "$44,320", "upl_fmt": "+$2,215 (+5.3%)", "upl_class": "good", "weight_fmt": "2.5%"},
                {"symbol": "AAPL", "strategy": "Mag7 Mom", "qty": "120", "avg_fmt": "$218.55", "cur_fmt": "$221.30", "mv_fmt": "$26,556", "upl_fmt": "+$330 (+1.3%)", "upl_class": "good", "weight_fmt": "1.5%"},
                {"symbol": "MSFT", "strategy": "Mag7 Mom", "qty": "85", "avg_fmt": "$432.20", "cur_fmt": "$438.65", "mv_fmt": "$37,285", "upl_fmt": "+$548 (+1.5%)", "upl_class": "good", "weight_fmt": "2.1%"},
                {"symbol": "META", "strategy": "Mag7 Mom", "qty": "40", "avg_fmt": "$612.40", "cur_fmt": "$628.10", "mv_fmt": "$25,124", "upl_fmt": "+$628 (+2.6%)", "upl_class": "good", "weight_fmt": "1.4%"},
                {"symbol": "GOOGL", "strategy": "Quality MR", "qty": "100", "avg_fmt": "$168.20", "cur_fmt": "$172.40", "mv_fmt": "$17,240", "upl_fmt": "+$420 (+2.5%)", "upl_class": "good", "weight_fmt": "1.0%"},
                {"symbol": "V", "strategy": "Quality MR", "qty": "80", "avg_fmt": "$282.10", "cur_fmt": "$285.50", "mv_fmt": "$22,840", "upl_fmt": "+$272 (+1.2%)", "upl_class": "good", "weight_fmt": "1.3%"},
                {"symbol": "QQQ", "strategy": "VIX Spike", "qty": "200", "avg_fmt": "$485.20", "cur_fmt": "$496.40", "mv_fmt": "$99,280", "upl_fmt": "+$2,240 (+2.3%)", "upl_class": "good", "weight_fmt": "5.5%"},
                {"symbol": "SPY", "strategy": "VIX Spike", "qty": "300", "avg_fmt": "$542.10", "cur_fmt": "$548.30", "mv_fmt": "$164,490", "upl_fmt": "+$1,860 (+1.1%)", "upl_class": "good", "weight_fmt": "9.1%"},
            ],
            "total_mv_fmt": "$437,135",
            "total_upl_fmt": "+$8,513 (+1.99%)",
            "total_upl_class": "good",
            "total_weight_fmt": "24.4%",
        },
        "feed": [
            {"time": "14:32:05", "side": "sell", "side_label": "SELL", "symbol": "NVDA",
             "detail": "50 sh @ $886.40 · Quality MR",
             "reasoning": "RSI 触及 78, 减仓 25%。NVDA 10 日内 +24%, 反弹幅度超 2σ, 历史回测此区间回撤概率 64%。剩余 150 股, 设动态止损 $886。",
             "pnl_fmt": "+$1,420", "pnl_class": "good"},
            {"time": "14:18:42", "side": "buy", "side_label": "BUY", "symbol": "META",
             "detail": "40 sh @ $612.40 · Mag7 Mom",
             "reasoning": "周一再平衡: 4 周回报 META +18% 进 top 3, 替换 TSLA (4w +3%)。卖 TSLA 30 股, 买 META 40 股, 等权。",
             "pnl_fmt": "+$420", "pnl_class": "good"},
            {"time": "14:11:30", "side": "hold", "side_label": "HOLD", "symbol": "AAPL",
             "detail": "接近财报, 无操作",
             "reasoning": "财报 7 天内, 历史隐含波动率从 24% 升至 38%。守住现有 120 股, 不加仓不减仓。财报日 5/21 之后复评。",
             "pnl_fmt": "$0", "pnl_class": ""},
            {"time": "14:02:11", "side": "buy", "side_label": "BUY", "symbol": "GOOGL",
             "detail": "100 sh @ $168.20 · Quality MR",
             "reasoning": "RSI(14) = 28 (低于阈值 30) + 价格 $167 跌破 50DMA $174。建仓 100 股 (0.9% 仓位), 止损 $159.50 (-5%)。",
             "pnl_fmt": "+$420", "pnl_class": "good"},
            {"time": "13:54:17", "side": "sell", "side_label": "SELL", "symbol": "TSLA",
             "detail": "30 sh @ $194.80 · Mag7 Mom 调仓",
             "reasoning": "4 周回报排名跌出 top 3 (Mag7 中第 5), 清仓以释放仓位给 META。",
             "pnl_fmt": "-$240", "pnl_class": "bad"},
            {"time": "13:42:08", "side": "add", "side_label": "ADD", "symbol": "V",
             "detail": "30 sh @ $282.10 · Quality MR 加仓",
             "reasoning": "RSI 反弹至 32 (从 25) 但仍在低位, 增加 30 股 (从 50 加到 80)。继续监控, RSI>50 时分批卖出。",
             "pnl_fmt": "+$102", "pnl_class": "good"},
        ],
        "risk": [
            {"k": "VaR (95%, 1d)", "v": "$22,400", "w_pct": 32},
            {"k": "Beta to SPY", "v": "1.08", "w_pct": 54},
            {"k": "净敞口", "v": "72.5%", "w_pct": 72},
            {"k": "Max DD (90d)", "v": "-2.4%", "w_pct": 18},
            {"k": "单仓集中度", "v": "9.1%", "w_pct": 30},
            {"k": "Sharpe (30d)", "v": "2.41", "w_pct": 82},
        ],
        "guardrails": [
            {"k": "单仓上限", "v": "≤ 10%", "meta": "最大 SPY 9.1%", "ok": True},
            {"k": "日内最大亏损", "v": "≤ 3%", "meta": "本日 -0.0%", "ok": True},
            {"k": "日内最大交易数", "v": "≤ 10", "meta": "已交易 7", "ok": True},
            {"k": "单笔最大金额", "v": "$5,000", "meta": "超过自动暂停", "ok": True},
            {"k": "交易时段", "v": "NYSE 常规", "meta": "09:30-16:00 ET", "ok": True},
            {"k": "止损必备", "v": "所有自动入场", "meta": "100% 覆盖", "ok": True},
            {"k": "新策略 paper", "v": "≥ 5 天", "meta": "默认开启", "ok": True},
            {"k": "熔断条件", "v": "日亏 -3%", "meta": "触发后 halt all", "ok": True},
        ],
    }


def main() -> int:
    env = Environment(
        loader=FileSystemLoader(str(TEMPLATES_DIR)),
        autoescape=select_autoescape(["html"]),
    )
    tpl = env.get_template("us-equity-desk.html")
    html = tpl.render(ctx=mock_ctx())
    OUT.write_text(html, encoding="utf-8")
    print(f"✓ rendered {len(html):,} chars → {OUT}")
    # quick structural sanity
    for needle in ["US Equity Desk", "Active Strategies", "Holdings (8)",
                   "Execution Feed", "Risk Cockpit", "Guardrails",
                   "NVDA", "Mag7 Momentum Rotation"]:
        assert needle in html, f"missing in render: {needle}"
    assert "{{" not in html, "unrendered Jinja expression remains"
    assert "{%" not in html, "unrendered Jinja block remains"
    print("✓ structural checks pass · no unrendered Jinja tags")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
