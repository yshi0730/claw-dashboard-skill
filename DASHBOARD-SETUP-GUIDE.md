# Dashboard Setup Guide (For Any Agent)

This guide tells any agent how to set up a visual dashboard for users. Copy this section into your agent's SKILL.md, or read it directly.

## Prerequisites

- Linux environment (ClawOS mini PC or any Ubuntu/Debian)
- Python 3.10+
- Internet connection (for tunnel registration)

## Setup Flow (Step by Step)

### Step 1: Clone the dashboard skill repo

```bash
git clone https://github.com/yshi0730/claw-dashboard-skill.git ~/.claw/dashboard-skill
```

### Step 2: Install dependencies

```bash
pip install fastapi uvicorn jinja2 httpx
```

### Step 3: Copy hub-app to ~/.claw/hub/

```bash
mkdir -p ~/.claw/{hub,config,shared}
cp -R ~/.claw/dashboard-skill/hub-app/* ~/.claw/hub/
```

### Step 4: Initialize the shared database

```python
import sqlite3, os

os.makedirs(os.path.expanduser('~/.claw/shared'), exist_ok=True)
db = sqlite3.connect(os.path.expanduser('~/.claw/shared/shared.db'))
db.executescript('''
    CREATE TABLE IF NOT EXISTS dashboard_modules (
        id TEXT PRIMARY KEY, agent_id TEXT NOT NULL, name TEXT NOT NULL,
        icon TEXT DEFAULT '📊', config TEXT DEFAULT '{}',
        created_at TEXT DEFAULT (datetime('now')), updated_at TEXT DEFAULT (datetime('now'))
    );
    CREATE TABLE IF NOT EXISTS dashboard_widgets (
        id TEXT PRIMARY KEY, module_id TEXT NOT NULL, widget_type TEXT NOT NULL,
        title TEXT NOT NULL, config TEXT DEFAULT '{}', data TEXT DEFAULT '[]',
        position INTEGER DEFAULT 0,
        created_at TEXT DEFAULT (datetime('now')), updated_at TEXT DEFAULT (datetime('now'))
    );
    CREATE TABLE IF NOT EXISTS dashboard_kv (
        namespace TEXT NOT NULL, key TEXT NOT NULL, value TEXT NOT NULL,
        updated_at TEXT DEFAULT (datetime('now')), PRIMARY KEY (namespace, key)
    );
''')
db.commit()
print('Database initialized')
```

### Step 5: Register device tunnel

```bash
mkdir -p ~/.claw/config
SERIAL=$(cat /sys/class/dmi/id/product_serial 2>/dev/null || echo "UNKNOWN")
curl -s -X POST https://api.clawln.app/devices/register \
  -H "Content-Type: application/json" \
  -d "{\"serial\": \"$SERIAL\"}" > ~/.claw/config/tunnel.json
```

### Step 6: Start hub server

```bash
cd ~/.claw/hub && nohup python3 -m uvicorn app:app --host 0.0.0.0 --port 3000 > ~/.claw/hub.log 2>&1 &
```

### Step 7: Start cloudflared tunnel

```bash
TUNNEL_TOKEN=$(python3 -c "import json,os; print(json.load(open(os.path.expanduser('~/.claw/config/tunnel.json')))['tunnel_token'])")
nohup cloudflared tunnel run --token "$TUNNEL_TOKEN" > ~/.claw/tunnel.log 2>&1 &
```

### Step 8: Register your module and add widgets

```python
import sqlite3, json, uuid, os

db = sqlite3.connect(os.path.expanduser('~/.claw/shared/shared.db'))

# Register your module (change agent_id, name, icon to match your agent)
module_id = str(uuid.uuid4())[:8]
db.execute(
    "INSERT OR IGNORE INTO dashboard_modules (id, agent_id, name, icon) VALUES (?, ?, ?, ?)",
    (module_id, "YOUR-AGENT-ID", "YOUR MODULE NAME", "📊")
)

# Add widgets — use any combination of these widget types:
# kpi_card, line_chart, bar_chart, pie_chart, table, activity_log, strategy_list, stat_row, text

# Example: KPI card
db.execute(
    "INSERT INTO dashboard_widgets (id, module_id, widget_type, title, config, data, position) VALUES (?, ?, ?, ?, ?, ?, ?)",
    (str(uuid.uuid4())[:8], module_id, "kpi_card", "Total Revenue",
     json.dumps({"prefix": "$", "trend": "up", "subtitle": "+12% vs last week"}),
     json.dumps([52000]), 0)
)

# Example: Activity log with AI reasoning
db.execute(
    "INSERT INTO dashboard_widgets (id, module_id, widget_type, title, config, data, position) VALUES (?, ?, ?, ?, ?, ?, ?)",
    (str(uuid.uuid4())[:8], module_id, "activity_log", "Agent Activity",
     json.dumps({}),
     json.dumps([
         {"time": "14:30", "action": "POST", "symbol": "TikTok", "qty": 1, "price": "",
          "strategy": "Content Plan", "logic": "Posted trending topic video. Hashtag #xyz has 2M views in 24h, engagement rate 8.5%."}
     ]), 1)
)

# Example: Table
db.execute(
    "INSERT INTO dashboard_widgets (id, module_id, widget_type, title, config, data, position) VALUES (?, ?, ?, ?, ?, ?, ?)",
    (str(uuid.uuid4())[:8], module_id, "table", "Recent Posts",
     json.dumps({}),
     json.dumps([
         {"Time": "04/23 14:30", "Content": "Trending topic video", "Views": "12.5K", "Likes": "1.2K", "Status": "Published"}
     ]), 2)
)

db.commit()
```

### Step 9: Tell user the URL

```python
import json, os
config = json.load(open(os.path.expanduser('~/.claw/config/tunnel.json')))
print(f"Your dashboard: {config['public_url']}")
```

## Available Widget Types

| Type | Data Format | Config Keys |
|------|-------------|-------------|
| `kpi_card` | `[value]` | `prefix`, `suffix`, `trend` ("up"/"down"), `subtitle`, `tag`, `tag_color` |
| `line_chart` | `[val1, val2, ...]` | `labels` (array), `color` (hex), `dataset_label`, `prefix` |
| `bar_chart` | `[val1, val2, ...]` | `labels`, `color` |
| `pie_chart` | `[val1, val2, ...]` | `labels`, `colors` (array of hex) |
| `table` | `[{col: val, ...}, ...]` | none (columns from object keys). Column named "Logic"/"Reasoning" renders as AI reasoning block |
| `activity_log` | `[{time, action, symbol, qty, price, strategy, logic}, ...]` | none. `logic` field renders as AI reasoning block |
| `strategy_list` | `[{name, description, status}, ...]` | none. `status`: "active" or "paused" |
| `stat_row` | `[{label, value}, ...]` | none |
| `text` | `["text content"]` | none |

## Updating Widget Data (Subsequent Sessions)

```python
# Find existing widgets
cursor = db.execute("SELECT id, title FROM dashboard_widgets WHERE module_id = ?", (module_id,))
for row in cursor:
    widget_id, title = row
    # Update data
    db.execute("UPDATE dashboard_widgets SET data = ?, updated_at = datetime('now') WHERE id = ?",
        (json.dumps([NEW_DATA]), widget_id))
db.commit()
```

## Using Custom HTML Instead of Widgets

If you want a completely custom dashboard design (not using the widget system), see the "Custom Templates" section below.

### Option A: Replace templates

Replace files in `~/.claw/hub/templates/` with your own Jinja2 templates. The FastAPI app at `~/.claw/hub/app.py` serves:
- `/` — renders `templates/index.html`
- `/m/{module_id}` — renders `templates/module.html`

Your templates can read from the SQLite database or any data source.

### Option B: Add static HTML

Place any HTML/CSS/JS files in `~/.claw/hub/public/`. They are served at `/static/`.
For a fully custom single-page app:

```bash
# Write your custom HTML
cat > ~/.claw/hub/public/custom.html << 'EOF'
<!DOCTYPE html>
<html>
<head><title>My Dashboard</title></head>
<body>
  <!-- Your custom design here -->
  <script>
    // Fetch data from the API
    fetch('/api/modules').then(r => r.json()).then(console.log);
    fetch('/api/modules/MODULE_ID/widgets').then(r => r.json()).then(console.log);
  </script>
</body>
</html>
EOF
```

Access at: `https://device-xxx.clawln.app/static/custom.html`

### Option C: Completely replace app.py

If you need full control, replace `~/.claw/hub/app.py` entirely with your own FastAPI app. The tunnel and domain still work — they just proxy to whatever is on port 3000.
