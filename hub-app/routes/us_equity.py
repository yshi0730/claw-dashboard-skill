"""GET /desk/us-equity — the fixed Alpaca US-equity dashboard.

Reads Alpaca creds from shared.db agent_config (written by the agent at
setup; see US-EQUITY-DASHBOARD-SCHEMA.md). If unconfigured, renders a
calm "connect your account" page instead of erroring. Any data-layer
failure also degrades to an error card, never a raw 500.
"""

from __future__ import annotations

import sqlite3
import traceback
from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import HTMLResponse
from jinja2 import Environment, FileSystemLoader, select_autoescape

from services.alpaca_client import AlpacaClient
from services.us_equity_context import build_context, read_alpaca_creds, AGENT_ID

CLAW_DIR = Path.home() / ".claw"
DB_PATH = CLAW_DIR / "shared" / "shared.db"
TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"

_env = Environment(
    loader=FileSystemLoader(str(TEMPLATES_DIR)),
    autoescape=select_autoescape(["html"]),
)

router = APIRouter()


def _shell(title: str, body: str) -> str:
    """Minimal dark page matching the dashboard aesthetic, for the
    not-configured / error states."""
    return f"""<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title}</title><style>
*{{box-sizing:border-box}}body{{margin:0;min-height:100vh;display:flex;
align-items:center;justify-content:center;font-family:Inter,'PingFang SC',
system-ui,sans-serif;background:radial-gradient(1000px 400px at 50% -10%,
rgba(75,226,173,.14),transparent),#0a1220;color:#edf3ff}}
.box{{max-width:520px;text-align:center;padding:40px;border:1px solid #294161;
border-radius:16px;background:#0f1b31}}
.mark{{width:48px;height:48px;border-radius:12px;margin:0 auto 18px;
background:linear-gradient(135deg,#4be2ad,#43b6ff);display:flex;
align-items:center;justify-content:center;font-size:22px;color:#0a1220;
font-weight:800}}
h1{{font-size:20px;margin:0 0 10px}}
p{{color:#94a9c7;font-size:13.5px;line-height:1.65;margin:8px 0 0}}
code{{background:#162843;padding:2px 7px;border-radius:5px;font-size:12px;
color:#4be2ad}}
</style></head><body><div class="box"><div class="mark">📈</div>
{body}</div></body></html>"""


@router.get("/desk/us-equity", response_class=HTMLResponse)
async def us_equity_desk():
    if not DB_PATH.exists():
        return HTMLResponse(_shell(
            "未配置 · US Equity",
            "<h1>仪表盘尚未初始化</h1><p>共享数据库还不存在。请先在 "
            "<code>US Stock Trader</code> agent 里完成配置。</p>",
        ))

    db = sqlite3.connect(str(DB_PATH))
    db.row_factory = sqlite3.Row
    try:
        creds = read_alpaca_creds(db, AGENT_ID)
        if not creds:
            return HTMLResponse(_shell(
                "未连接 Alpaca · US Equity",
                "<h1>还没连接 Alpaca 账户</h1><p>请在 "
                "<code>US Stock Trader</code> agent 里提供你的 Alpaca "
                "API key。配置完成后这个页面会自动显示你的实时组合、"
                "策略和风控。</p>",
            ))
        try:
            with AlpacaClient(
                creds["key"], creds["secret"], paper=creds["paper"]
            ) as ac:
                ctx = build_context(ac, db)
        except Exception as e:  # noqa: BLE001
            return HTMLResponse(_shell(
                "数据加载失败 · US Equity",
                f"<h1>暂时拿不到数据</h1><p>连接 Alpaca 或读取数据时出错："
                f"<br><code>{type(e).__name__}: {str(e)[:160]}</code><br><br>"
                f"通常是 API key 失效或 Alpaca 临时不可用，稍后刷新重试。</p>",
            ), status_code=200)

        tpl = _env.get_template("us-equity-desk.html")
        return HTMLResponse(tpl.render(ctx=ctx))
    except Exception:  # noqa: BLE001 — last-resort guard, never raw 500
        return HTMLResponse(_shell(
            "渲染错误 · US Equity",
            f"<h1>页面渲染出错</h1><p><code>"
            f"{traceback.format_exc().splitlines()[-1][:200]}</code></p>",
        ), status_code=200)
    finally:
        db.close()
