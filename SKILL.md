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

## How This Skill Works

This skill is **referenced by other agents** (like a stock trader or e-commerce manager). When the parent agent needs to show data visually, it uses your tools.

## Setup Flow

When an agent first needs a dashboard:

1. Call `dashboard_status` — check if hub is already running
2. If not set up, call `dashboard_setup` — this installs the hub, cloudflared, registers the device, and starts services
3. Tell the user their dashboard URL
4. Call `dashboard_register_module` — register the agent's page
5. Call `dashboard_add_widget` — add charts, tables, KPI cards

**The setup is one-time and automatic.** After first setup, agents just register modules and push data.

## Widget Types

| Type | Use Case | Data Format |
|------|----------|-------------|
| `kpi_card` | Single key metric | `[value]` + config: `{prefix, suffix, trend, subtitle}` |
| `line_chart` | Trends over time | `[val1, val2, ...]` + config: `{labels, color, dataset_label}` |
| `bar_chart` | Comparisons | `[val1, val2, ...]` + config: `{labels, color}` |
| `pie_chart` | Proportions | `[val1, val2, ...]` + config: `{labels, colors}` |
| `table` | Detailed data | `[{col1: val, col2: val}, ...]` |
| `text` | Notes/alerts | `["text content"]` |
| `stat_row` | Multiple small stats | `[{label, value}, ...]` |

## Example: Stock Trading Agent Adding Dashboard

```
1. dashboard_setup()
   → Hub installed, tunnel started
   → URL: https://device-abc123.clawln.app

2. dashboard_register_module(agent_id="futu-stock", name="持仓面板", icon="📈")
   → Module registered, ID: "m1a2b3"

3. dashboard_add_widget(module_id="m1a2b3", widget_type="kpi_card",
     title="Portfolio Value", data=[125000],
     config={prefix: "¥", trend: "up", subtitle: "+2.3% today"})

4. dashboard_add_widget(module_id="m1a2b3", widget_type="line_chart",
     title="30-Day PnL", data=[100, 102, 98, 105, 110, ...],
     config={labels: ["3/1", "3/2", ...], color: "#22c55e"})

5. dashboard_add_widget(module_id="m1a2b3", widget_type="table",
     title="Open Positions",
     data=[
       {symbol: "00700.HK", name: "腾讯", qty: 1000, pnl: "+¥3,200"},
       {symbol: "AAPL", name: "Apple", qty: 50, pnl: "-$120"},
     ])
```

## Shared Data

Agents can share data via the key-value store:

```
dashboard_push_data(namespace="ecommerce", key="daily_revenue", value={"today": 5200, "yesterday": 4800})
dashboard_get_data(namespace="ecommerce", key="daily_revenue")
```

Other agents can read this data to cross-reference (e.g., a finance agent reading e-commerce revenue).

## Updating Data

Agents should periodically update widget data:

```
dashboard_update_widget(widget_id="w1", data=[new_value])
```

This keeps the dashboard fresh. Suggested update frequency:
- KPI cards: every session or when data changes
- Charts: daily or when new data points arrive
- Tables: every session

## Important Rules

- **Never expose tunnel tokens or credentials in chat**
- **Don't remove widgets without asking the user**
- **Always show the public URL after setup** so user can bookmark it
- **Dashboard works locally** at `http://localhost:3000` even without internet
- **Multiple agents share one dashboard** — each gets its own module/page
