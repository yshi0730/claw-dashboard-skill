# USER.md - How to Use

## What This Skill Does

This skill gives your agent the ability to build and serve a **visual dashboard** — a real website you can open on your phone or laptop to see your data.

## How It Works

1. Your agent asks if you want a dashboard
2. You say yes — setup takes about 1 minute
3. You get a stable URL like `https://device-xxx.clawln.app`
4. Open it from anywhere — phone, laptop, anywhere with internet
5. Your agent populates the dashboard with relevant data

## What You'll See

- **KPI Cards** — key numbers at a glance (account value, daily sales, etc.)
- **Charts** — line charts, bar charts for trends
- **Tables** — detailed data in sortable tables
- **Multiple pages** — each agent gets its own section

## Requirements

- Internet connection (for initial setup and remote access)
- Python 3.10+
- ~100MB disk space for hub + cloudflared

## FAQ

**Q: Is my data safe?**
A: Yes. All data stays on your device in a local database. The URL is just a secure tunnel — no data is stored in the cloud.

**Q: Can I access it without internet?**
A: Yes, locally at `http://localhost:3000`. The public URL needs internet.

**Q: What if I restart my machine?**
A: The dashboard auto-restarts. Your URL stays the same.
