---
name: dashboard
description: Build and serve visual dashboards for any agent — install hub, register modules, add widgets, push data, accessible from anywhere via stable URL.
version: 0.1.0
user-invocable: true
metadata:
  openclaw:
    emoji: "📊"
    requires:
      bins: [python3]
---

# Claw Dashboard Skill

You are a **dashboard builder**. You help other agents create visual dashboards that users can view in their browser from anywhere.

This skill is **referenced by other agents** (stock trader, crypto trader, e-commerce manager, etc.). When the parent agent needs to show data visually, it uses your tools.

---

## Complete Tool Reference

### Setup Tools

#### `dashboard_setup`
One-time setup: installs hub + cloudflared, registers device, starts services.
```json
{"serial": "ABCDEF123456"}
```
- `serial` (optional): 12-char device serial. Auto-detected on ClawOS. Pass manually if auto-detect fails.
- Returns: `{"status": "ready", "public_url": "https://device-xxx.clawln.app", "local_url": "http://localhost:3000"}`
- Idempotent: safe to call multiple times.

#### `dashboard_status`
Check if hub is installed, running, and tunnel is active.
```json
{}
```
Returns: `{"hub": {"installed": true, "running": true, "healthy": true}, "tunnel": {"running": true, "public_url": "..."}, "serial": "..."}`

#### `dashboard_restart`
Restart hub and tunnel services.

#### `dashboard_get_url`
Get the public and local dashboard URLs.

### Module Tools

#### `dashboard_register_module`
Register a page for your agent on the dashboard. **Each agent registers exactly one module.**
```json
{"agent_id": "futu-stock-trader", "name": "持仓面板", "icon": "📈"}
```
- Idempotent: if module already exists for this `agent_id`, returns existing module ID.
- Returns: `{"module_id": "abc123", "status": "registered"}`

#### `dashboard_list_modules`
List all registered modules (all agents' pages).

#### `dashboard_remove_module`
Remove a module and ALL its widgets. **Always confirm with user first.**

### Widget Tools

#### `dashboard_add_widget`
Add a widget to a module.
```json
{
  "module_id": "abc123",
  "widget_type": "kpi_card",
  "title": "Portfolio Value",
  "config": {"prefix": "¥", "trend": "up", "subtitle": "+2.3% today"},
  "data": [125000]
}
```
Returns: `{"widget_id": "w001", "status": "created"}`

#### `dashboard_update_widget`
Update an existing widget's data and/or config. **Use this to refresh data, not `dashboard_add_widget`.**
```json
{
  "widget_id": "w001",
  "data": [128000],
  "config": {"subtitle": "+4.5% today"}
}
```
- `config` is **merged** with existing config (not replaced).
- `data` is **replaced** entirely.

#### `dashboard_remove_widget`
Remove a single widget.

#### `dashboard_list_widgets`
List all widgets in a module. Use this to check what already exists.
```json
{"module_id": "abc123"}
```

### Shared Data Tools

#### `dashboard_push_data`
Write a key-value pair to shared storage. Other agents can read it.
```json
{"namespace": "ecommerce", "key": "daily_revenue", "value": {"today": 5200, "yesterday": 4800}}
```

#### `dashboard_get_data`
Read a key-value pair from shared storage.
```json
{"namespace": "ecommerce", "key": "daily_revenue"}
```

---

## Widget Type Reference

### `kpi_card` — Single Key Metric

**Config keys:**
| Key | Type | Example | Description |
|-----|------|---------|-------------|
| `prefix` | string | `"¥"`, `"$"`, `""` | Text before the value |
| `suffix` | string | `"%"`, `" BTC"` | Text after the value |
| `trend` | string | `"up"` or `"down"` | Green (up) or red (down) coloring |
| `subtitle` | string | `"+2.3% today"` | Small text below the value |

**Data:** `[single_value]` — one number or string.

```json
{
  "widget_type": "kpi_card",
  "title": "Account Value",
  "config": {"prefix": "$", "trend": "up", "subtitle": "+$320 unrealized"},
  "data": [12500]
}
```

### `line_chart` — Trends Over Time

**Config keys:**
| Key | Type | Example | Description |
|-----|------|---------|-------------|
| `labels` | string[] | `["Mon","Tue","Wed"]` | X-axis labels |
| `color` | string | `"#22c55e"` | Line color (hex) |
| `bg_color` | string | `"rgba(34,197,94,0.1)"` | Fill color under line |
| `dataset_label` | string | `"PnL"` | Legend label |

**Data:** `[val1, val2, val3, ...]` — array of numbers, one per label.

```json
{
  "widget_type": "line_chart",
  "title": "30-Day Equity Curve",
  "config": {"labels": ["4/1","4/5","4/10","4/15","4/20"], "color": "#22c55e", "dataset_label": "Equity"},
  "data": [10000, 10800, 10500, 11800, 12500]
}
```

### `bar_chart` — Comparisons

**Config keys:** Same as `line_chart`.

**Data:** `[val1, val2, ...]`

```json
{
  "widget_type": "bar_chart",
  "title": "Monthly Sales by Category",
  "config": {"labels": ["Electronics","Clothing","Food","Books"], "color": "#6366f1"},
  "data": [45000, 32000, 28000, 15000]
}
```

### `pie_chart` — Proportions

**Config keys:**
| Key | Type | Example | Description |
|-----|------|---------|-------------|
| `labels` | string[] | `["BTC","ETH","SOL"]` | Slice labels |
| `colors` | string[] | `["#f59e0b","#6366f1","#22c55e"]` | Slice colors (auto-assigned if omitted) |

**Data:** `[val1, val2, ...]` — one value per slice.

```json
{
  "widget_type": "pie_chart",
  "title": "Portfolio Allocation",
  "config": {"labels": ["BTC","ETH","SOL","USDC"], "colors": ["#f59e0b","#6366f1","#22c55e","#94a3b8"]},
  "data": [45, 25, 15, 15]
}
```

### `table` — Detailed Data

**Config keys:** None needed.

**Data:** `[{col1: val, col2: val}, ...]` — array of row objects. Column names come from object keys.

```json
{
  "widget_type": "table",
  "title": "Open Positions",
  "data": [
    {"Symbol": "00700.HK", "Name": "腾讯", "Qty": 1000, "Price": "380.00", "PnL": "+¥3,200"},
    {"Symbol": "AAPL", "Name": "Apple", "Qty": 50, "Price": "$198.50", "PnL": "-$120"}
  ]
}
```

### `text` — Notes or Alerts

**Config keys:** None.

**Data:** `["text content here — supports plain text"]`

```json
{
  "widget_type": "text",
  "title": "Morning Briefing",
  "data": ["BTC +1.2% overnight. ETH funding rate high at 0.08%. SOL momentum signal triggered."]
}
```

### `stat_row` — Multiple Small Stats in a Row

**Config keys:** None.

**Data:** `[{"label": "...", "value": "..."}, ...]`

```json
{
  "widget_type": "stat_row",
  "title": "Key Metrics",
  "data": [
    {"label": "Win Rate", "value": "62%"},
    {"label": "Sharpe", "value": "1.85"},
    {"label": "Max DD", "value": "-8.2%"},
    {"label": "Profit Factor", "value": "2.1"}
  ]
}
```

---

## Agent Integration Flow

### First Session (Dashboard Not Yet Set Up)

```
1. Call dashboard_status()
   → hub.installed = false

2. ASK USER: "需要我帮你搭建一个可视化面板吗？你可以在浏览器里随时查看数据。"
   → User says yes

3. Call dashboard_setup()  (or dashboard_setup(serial="...") if auto-detect fails)
   → Returns public_url

4. TELL USER: "Dashboard 已就绪：https://device-xxx.clawln.app，建议收藏。"

5. Call dashboard_register_module(agent_id="your-agent-id", name="显示名", icon="📈")
   → Returns module_id

6. Call dashboard_add_widget(...) for each initial widget
   → KPI cards, charts, tables as appropriate for your domain

7. TELL USER: "面板已搭建好，包含 X 个组件，打开链接即可查看。"
```

### Subsequent Sessions (Dashboard Already Running)

```
1. Call dashboard_status()
   → hub.running = true, public_url exists

2. Call dashboard_register_module(agent_id="your-agent-id", name="...", icon="...")
   → Returns already_registered = true, module_id

3. Call dashboard_list_widgets(module_id="...")
   → Get list of existing widgets with their IDs

4. For each widget that needs fresh data:
   Call dashboard_update_widget(widget_id="...", data=[new_data])
   (DO NOT call dashboard_add_widget — that creates duplicates!)

5. If new widgets are needed (e.g., user asked for a new chart):
   Call dashboard_add_widget(...)
```

### Error Handling

```
dashboard_setup() fails:
  → Check error message. Common issues:
    - "Could not determine device serial number" → ask user for serial, retry with serial param
    - Network error → check internet, retry
    - "tunnel_creation_failed" → registration API issue, retry later

dashboard_status() shows hub.running = false:
  → Call dashboard_restart()
  → If still fails, call dashboard_setup() to reinstall

dashboard_update_widget() returns "Widget not found":
  → Widget was deleted. Call dashboard_add_widget() to recreate it.
```

---

## Domain-Specific Examples

### Stock Trading Agent (Futu / Alpaca)

```
Module: dashboard_register_module(agent_id="futu-stock-trader", name="持仓面板", icon="📈")

Widgets:
1. kpi_card: "Portfolio Value" — data=[125000], config={prefix:"¥", trend:"up", subtitle:"+2.3%"}
2. kpi_card: "Today's PnL" — data=[2800], config={prefix:"¥", trend:"up"}
3. line_chart: "Equity Curve (30d)" — data=[100k, 105k, ...], config={labels:[dates], color:"#22c55e"}
4. table: "Open Positions" — data=[{Symbol, Name, Qty, AvgCost, LastPrice, PnL, PnL%}]
5. table: "Recent Trades" — data=[{Time, Symbol, Side, Qty, Price, Status}]
6. stat_row: "Performance" — data=[{Win Rate, 62%}, {Sharpe, 1.85}, {Max DD, -8.2%}]
7. pie_chart: "Sector Allocation" — data=[40,25,20,15], config={labels:["Tech","Finance","Healthcare","Energy"]}
```

### Crypto Trading Agent (Hyperliquid)

```
Module: dashboard_register_module(agent_id="hyperliquid-trader", name="Crypto Dashboard", icon="🔮")

Widgets:
1. kpi_card: "Account Equity" — data=[12500], config={prefix:"$", trend:"up", subtitle:"Mainnet"}
2. kpi_card: "Unrealized PnL" — data:[320], config={prefix:"$", trend:"up"}
3. kpi_card: "Daily Funding Paid" — data:[-15.60], config={prefix:"$", trend:"down", subtitle:"net funding"}
4. line_chart: "PnL (7d)" — data=[...], config={labels:[dates], color:"#6366f1"}
5. table: "Open Perp Positions" — data=[{Coin, Side, Size, Entry, Mark, Liq.Price, PnL, Leverage}]
6. table: "Spot Balances" — data=[{Token, Amount, Value}]
7. stat_row: "Risk" — data=[{Leverage, "5.2x"}, {Margin Used, "42%"}, {Distance to Liq, "18%"}]
8. bar_chart: "Funding Rate (Top 5)" — data=[0.08, 0.05, 0.03, -0.01, -0.02], config={labels:["BTC","ETH","SOL","DOGE","ARB"]}
```

### Prediction Market Agent (Polymarket)

```
Module: dashboard_register_module(agent_id="polymarket-trader", name="Predictions", icon="🎯")

Widgets:
1. kpi_card: "Portfolio Value" — data=[8500], config={prefix:"$", trend:"up"}
2. kpi_card: "Active Positions" — data=[12], config={suffix:" markets"}
3. kpi_card: "Win Rate" — data:[68], config={suffix:"%", trend:"up"}
4. table: "Open Positions" — data=[{Market, Position, Shares, AvgCost, CurrentPrice, Edge, PnL}]
5. line_chart: "Equity Curve" — data=[...], config={labels:[dates], color:"#22c55e"}
6. pie_chart: "By Category" — data=[35,25,20,15,5], config={labels:["Politics","Crypto","Sports","Weather","Other"]}
7. table: "Recent Resolutions" — data=[{Market, Result, PnL, Date}]
8. stat_row: "Stats" — data=[{Brier Score, "0.18"}, {ROI, "+22%"}, {Avg Edge, "8.5%"}]
```

### E-Commerce Agent

```
Module: dashboard_register_module(agent_id="ecommerce-manager", name="店铺数据", icon="🛒")

Widgets:
1. kpi_card: "Today's Revenue" — data=[5200], config={prefix:"¥", trend:"up", subtitle:"+8% vs yesterday"}
2. kpi_card: "Orders Today" — data=[47], config={trend:"up"}
3. kpi_card: "Conversion Rate" — data:[3.2], config={suffix:"%", trend:"down", subtitle:"-0.3% vs last week"}
4. line_chart: "Revenue (30d)" — data=[...], config={labels:[dates], color:"#f59e0b", dataset_label:"Revenue"}
5. bar_chart: "Top Products" — data=[120, 95, 80, 65, 40], config={labels:["Product A","B","C","D","E"]}
6. table: "Recent Orders" — data=[{OrderID, Customer, Items, Amount, Status, Time}]
7. pie_chart: "Revenue by Channel" — data=[45,30,25], config={labels:["Taobao","JD","Douyin"]}
8. stat_row: "Overview" — data=[{Avg Order, "¥110"}, {Return Rate, "2.1%"}, {Reviews, "4.8★"}]
```

---

## Important Rules

1. **Always ask user first** — never auto-setup dashboard without user confirmation
2. **Never expose tunnel tokens or credentials** in chat, logs, or git
3. **Don't remove widgets** without asking the user
4. **Always show the public URL** after setup so user can bookmark it
5. **Use `dashboard_update_widget` for refreshing data**, not `dashboard_add_widget` (which creates duplicates)
6. **Call `dashboard_list_widgets` at start of each session** to know what exists
7. **Dashboard works locally** at `http://localhost:3000` even without internet
8. **Multiple agents share one dashboard** — each gets its own module/page, don't touch other agents' modules
9. **Keep widget count reasonable** — 5-8 widgets per module is ideal. Don't overwhelm the user.
10. **Update data every session** — stale dashboards are worse than no dashboard
