# Onboarding State Machine (Shared)

**This document is the canonical onboarding flow for any OpenClaw agent that uses Workspace + Dashboard.** Each agent's SKILL.md bundles a copy of this file (or symlinks to it) and the model reads it on every wake-up.

The states defined here are **MANDATORY**. Agents must not skip, reorder, or merge states. Doing so is the most common cause of bad onboarding UX (e.g., the agent re-introduces itself when the user is already in S6, or asks for an API key before the dashboard exists).

---

## 1. State Detection — Run This First

On every wake-up, check these two signals **in order**, then look up your state in the table below.

### Signal 1: Does the workspace path exist?

```bash
test -d "{WORKSPACE_PATH}/skills/storyclaw-workspace-reporter/" && echo "yes" || echo "no"
```

`{WORKSPACE_PATH}` is **agent-specific** (defined in each SKILL.md). Examples:
- Alpaca: `/home/storyclaw/.openclaw/workspace-alpaca-us-stock-trader`
- Futu: `/home/storyclaw/.openclaw/workspace-futu-stock-trader`
- Hyperliquid: `/home/storyclaw/.openclaw/workspace-hyperliquid-trader`
- Polymarket: `/home/storyclaw/.openclaw/workspace-polymarket-trader`

### Signal 2: Does the agent_state row exist?

```python
import sqlite3, os
db_path = os.path.expanduser('~/.claw/shared/shared.db')
state_row = None
if os.path.exists(db_path):
    db = sqlite3.connect(db_path)
    cur = db.execute(
        "SELECT state, mode, strategy_template FROM agent_state WHERE agent_id = ?",
        ("{AGENT_ID}",)
    )
    state_row = cur.fetchone()
```

If the table doesn't exist yet, treat as "no row". You'll create the table in §S3.

### State Lookup Table

| Workspace? | agent_state row? | Pre-S3 marker file? | State | Go to |
|-----------|------------------|---------------------|-------|-------|
| ✗ | n/a | ✗ | **S1** First intro | §S1 |
| ✗ | n/a | ✓ | **S2** Awaiting workspace | §S2 |
| ✓ | ✗ | n/a | **S3** Auto-produce | §S3 |
| ✓ | state="S4_choosing" | n/a | **S4** Mode choice | §S4 |
| ✓ | state="S5a_live_setup" | n/a | **S5a** Live setup | §S5a |
| ✓ | state="S5b_surprise" | n/a | **S5b** Surprise mode | §S5b |
| ✓ | state="S6_running" | n/a | **S6** Running | §S6 |
| ✓ | state="S6_paused" | n/a | **S6.paused** | §S6 (paused branch) |

The "pre-S3 marker file" is `~/.openclaw/agent-state/{AGENT_ID}.json`. It exists if the agent already introduced itself once but workspace was never installed.

---

## §S1 — First Intro

**Single-turn action.** The agent has never spoken to this user before. Workspace does not exist. No state file exists.

### What to do

1. Output the **MANDATORY S1 template** defined in your agent's SKILL.md, verbatim. Do not paraphrase, do not add sections, do not omit sections.
2. Create the pre-S3 marker file so next session knows this user has been introduced:
   ```bash
   mkdir -p ~/.openclaw/agent-state
   echo '{"introduced": true, "introduced_at": "'$(date -Iseconds)'"}' > ~/.openclaw/agent-state/{AGENT_ID}.json
   ```
3. Stop. Do not continue with any other action. Wait for user response.

### What is FORBIDDEN in S1

These are the most common ways agents break S1. Do not do any of them:

- ❌ Asking what the user wants ("你想交易什么?", "What do you want to do?")
- ❌ Listing "quick start" commands the user could try
- ❌ Offering to build a dashboard (S3 does this automatically)
- ❌ Asking for any API key, credential, or configuration
- ❌ Disclaiming autonomous capabilities ("I won't trade without confirmation" — wrong, you DO support automation)
- ❌ Adding capabilities or sections not in the template
- ❌ Going over the template length (the template is calibrated to be scannable)

The S1 template is short on purpose. The user's only next action should be clicking "Install Workspace".

---

## §S2 — Awaiting Workspace

User has been introduced but workspace still not installed. Don't repeat the full intro.

### Template (use as-is, translate to user language)

```
我需要你先装工作区才能继续 —— 请点右侧"工作区"卡片 → 安装。
装好之后我立刻给你搭 dashboard 和样例报告。
```

### After 2 reminders, fallback

If the user has been reminded twice and still hasn't installed workspace, offer a degraded mode:

```
看起来你暂时不想装工作区也没问题。这种模式下我只能在聊天里给你建议和分析，没法做可视化面板和归档报告。

如果之后想要完整体验，随时装上工作区就行。

现在我们直接进入配置吧 —— 你想用真钱还是先试试纸面交易？
```

In degraded mode, skip §S3 entirely and go directly to §S4 mode choice. Set `agent_state.state = "S4_choosing"` and `agent_state.mode_hint = "degraded"`.

---

## §S3 — Auto-Produce (DO NOT ASK USER)

Workspace exists. No agent_state row. This is your one chance to wow the user — they just installed workspace, now they expect something to happen.

### Execute this sequence in ONE turn — no questions to user

1. **Initialize dashboard infrastructure** — Follow `DASHBOARD-SETUP-GUIDE.md` steps 1-7. Use the agent-specific values from your SKILL.md:
   - `agent_id`: `{AGENT_ID}`
   - `module_name`: `{MODULE_NAME}`
   - `icon`: `{MODULE_ICON}`

2. **Create the dashboard widgets** — Use the "Dashboard Template" section in your agent's SKILL.md. **Populate with realistic sample data**, not zeros. The user is looking at this for the first time and needs to understand what it'll show.

3. **Create the sample report file** in workspace:
   - Path: `{WORKSPACE_PATH}/files/sample-report.html`
   - Content: A polished mock weekly report — sample trades, P&L curve, AI reasoning blocks, guardrail status, etc. This is the "this is what you'll get every week" preview.

4. **Create the agent_state table** (if not exists) and write the first row:
   ```sql
   CREATE TABLE IF NOT EXISTS agent_state (
     agent_id TEXT PRIMARY KEY,
     state TEXT NOT NULL,
     mode TEXT,
     strategy_template TEXT,
     paper_key_provided INTEGER DEFAULT 0,
     surprise_started_at TEXT,
     updated_at TEXT DEFAULT (datetime('now'))
   );
   INSERT OR REPLACE INTO agent_state (agent_id, state, updated_at)
   VALUES ('{AGENT_ID}', 'S4_choosing', datetime('now'));
   ```

5. **Send ONE message to the user** — combine the dashboard URL, the sample report announcement, and the A/B choice:

```
✅ 都搭好啦！

📱 Dashboard: {DASHBOARD_URL}
📄 样例报告：右侧工作区里的 sample-report.html

现在选个开始方式：

[ A ] 🔐 我有自己的账户 —— 用真钱（先纸面试跑几天再上真钱）
[ B ] 🎁 Surprise Me —— 你帮我选个策略，用纸面账户跑起来

选 A 还是 B？
```

The two-button framing is **mandatory**. Don't offer 3+ options. Don't accept "I want to do X specific thing" — if user gets specific, gently redirect to A.

---

## §S4 — Mode Choice

User's response to the A/B prompt. Parse strictly:

- "A" / "真钱" / "live" / "我有账户" / "我自己来" → go to §S5a
- "B" / "Surprise" / "随便" / "你来" / "随机" / "试试看" → go to §S5b
- Anything ambiguous → re-show the 2 buttons. Don't take free-form strategy input here.

After parsing, update state:

```sql
UPDATE agent_state SET state = 'S5a_live_setup' WHERE agent_id = '{AGENT_ID}';
-- OR
UPDATE agent_state SET state = 'S5b_surprise' WHERE agent_id = '{AGENT_ID}';
```

---

## §S5a — Live Setup (Real Money)

User chose A. Now we set them up for live trading. **Still enforce paper-first** — they trade real money only after a paper validation period.

### Sequence

1. Walk through your agent's existing setup flow (API keys, account configuration). Use existing setup tools from your skill.
2. Ask user to pick a **risk tolerance**: 低 / 中 / 高 — this maps to guardrail presets (see your skill's Guardrails section).
3. Ask user to pick an **authorization level**: Advisory / Semi-Auto / Full Auto (default Semi-Auto). See your skill's Authorization Levels section.
4. Discuss strategy — use your skill's existing Strategy Lifecycle (DISCUSS → BUILD → BACKTEST → PAPER → REVIEW → LIVE → RUN).
5. **Mandatory paper trial** — run on paper for N days before going live (N from guardrails, default 5).
6. After paper trial passes and user approves live: switch keys to live, update `agent_state.mode = 'live'`, update `agent_state.state = 'S6_running'`.

---

## §S5b — Surprise Me

User chose B. Run the surprise sequence. Use the paper signup steps + strategy pool from your agent's SKILL.md.

### Sequence

1. **Get paper account credentials** — Output the paper signup steps from your SKILL.md verbatim. Wait for user to paste paper API key.

2. **Pick exactly ONE strategy** from your SKILL.md's "Surprise Me Strategy Pool". Pick based on current market conditions (each strategy has a "selection condition" in the pool table). **Don't combine, don't invent.**

3. **Tell user which strategy you picked and why** — One paragraph, no follow-up questions:
   ```
   我给你跑这个策略：**{STRATEGY_NAME}**
   
   选这个的原因：{ONE_SENTENCE_REASONING_BASED_ON_MARKET}
   
   规则：{ONE_PARAGRAPH_STRATEGY_LOGIC}
   
   风控：max position 20%, max daily loss 3%, 止损 -X%（按策略）。
   ```

4. **Set guardrails to defaults** from your skill's Guardrails table. Don't ask user to customize — this is Surprise Me.

5. **Activate immediately** on paper account with Authorization Level 2 (Full Auto). Strategy starts running now.

6. **Update dashboard** — Add a `text` widget at position 0:
   ```
   🟡 模拟模式 (Paper Trading) —— 用纸面账户跑，零风险。表现满意可随时切真钱。
   ```

7. **Update state**:
   ```sql
   UPDATE agent_state SET 
     state = 'S6_running',
     mode = 'paper',
     strategy_template = '{STRATEGY_NAME}',
     surprise_started_at = datetime('now'),
     paper_key_provided = 1
   WHERE agent_id = '{AGENT_ID}';
   ```

8. **Schedule a 7-day check-in** — After 7 days of running, proactively message:
   ```
   纸面账户跑了 7 天了 ✅
   
   绩效：{PAPER_PNL_SUMMARY}（详见 dashboard）
   
   要切真钱继续跑这个策略吗？想的话把 live API key 给我（不是 paper key）。
   ```
   
   If user agrees → switch to §S5a but skip strategy discussion, reuse current strategy. If user says "继续试试" → keep running paper indefinitely. If user says no → ask if they want to try a different surprise strategy or stop.

---

## §S6 — Running

The agent is operational. Strategies are executing, dashboard is updating, weekly reports are being archived.

### Rules in S6

- **No more onboarding questions.** Do not re-introduce yourself. Do not ask "would you like a dashboard?" — it exists. Do not ask about authorization level — already set.
- **Follow your skill's existing operational sections**: Strategy Lifecycle, Daily Autonomous Summary, Overnight Research & Morning Briefing.
- **Update the dashboard every session** with fresh data (strategy P&L, recent trades with AI reasoning, guardrail status).
- **Archive a weekly report to workspace** — every 7 days, write a new report file to `{WORKSPACE_PATH}/files/week-YYYYMMDD.html`.
- **Respect guardrail breaches** — if a guardrail trips, halt execution and notify user immediately, regardless of authorization level.

### Adding more strategies in S6

If user wants another strategy: discuss + backtest + paper trial + activate. Don't restart onboarding.

### Pausing

User says "暂停" / "pause" / "stop trading":
```sql
UPDATE agent_state SET state = 'S6_paused' WHERE agent_id = '{AGENT_ID}';
```
Halt all strategy execution. Keep dashboard, keep reports. Wait for user to resume.

User says "resume" / "继续" / "重启":
```sql
UPDATE agent_state SET state = 'S6_running' WHERE agent_id = '{AGENT_ID}';
```
Resume strategy execution from current state.

---

## State Schema (Reference)

```sql
CREATE TABLE IF NOT EXISTS agent_state (
    agent_id TEXT PRIMARY KEY,
    state TEXT NOT NULL,         -- S2_awaiting_workspace | S4_choosing | S5a_live_setup | S5b_surprise | S6_running | S6_paused
    mode TEXT,                   -- 'paper' | 'live' | 'degraded'
    strategy_template TEXT,      -- name of Surprise Me strategy (or NULL for live custom strategies)
    paper_key_provided INTEGER DEFAULT 0,
    surprise_started_at TEXT,    -- ISO timestamp, used for 7-day check-in
    updated_at TEXT DEFAULT (datetime('now'))
);
```

Pre-S3 marker file at `~/.openclaw/agent-state/{AGENT_ID}.json`:
```json
{
  "introduced": true,
  "introduced_at": "2026-05-12T15:00:00+08:00"
}
```

---

## Variable Glossary

These variables appear in this doc as `{VARIABLE_NAME}`. Each agent's SKILL.md defines its values.

| Variable | Defined in | Example (Alpaca) |
|----------|-----------|------------------|
| `{AGENT_ID}` | SKILL.md → "Agent Variables" block | `alpaca-us-stock-trader` |
| `{WORKSPACE_PATH}` | SKILL.md → "Agent Variables" block | `/home/storyclaw/.openclaw/workspace-alpaca-us-stock-trader` |
| `{MODULE_NAME}` | SKILL.md → "Agent Variables" block | `美股交易面板` |
| `{MODULE_ICON}` | SKILL.md → "Agent Variables" block | `📈` |
| `{DASHBOARD_URL}` | Produced at §S3 from tunnel.json | `https://device-xxx.clawln.app` |
| MANDATORY S1 template | SKILL.md → "§S1 Template" block | Agent-specific text |
| Paper signup steps | SKILL.md → "§S5b Paper Signup" block | Agent-specific text |
| Surprise Me strategy pool | SKILL.md → "Surprise Me Strategy Pool" block | Agent-specific table |
| Dashboard widget template | SKILL.md → "Dashboard Template" block | Agent-specific widget list |
