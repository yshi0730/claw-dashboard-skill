"""Module registration tools — agents register their dashboard pages."""

from __future__ import annotations

import json
import uuid
from mcp.server import Server
from mcp.types import Tool, TextContent

from ..storage.db import get_db


def register_module_tools(server: Server):

    def _tools() -> list[Tool]:
        return [
            Tool(
                name="dashboard_register_module",
                description="Register a dashboard module (page) for an agent. Each agent should register one module.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "agent_id": {"type": "string", "description": "Agent skill ID (e.g. 'ecommerce-skill')"},
                        "name": {"type": "string", "description": "Display name for the module (e.g. '电商面板')"},
                        "icon": {"type": "string", "description": "Emoji icon", "default": "📊"},
                    },
                    "required": ["agent_id", "name"],
                },
            ),
            Tool(
                name="dashboard_list_modules",
                description="List all registered dashboard modules",
                inputSchema={"type": "object", "properties": {}},
            ),
            Tool(
                name="dashboard_remove_module",
                description="Remove a dashboard module and all its widgets",
                inputSchema={
                    "type": "object",
                    "properties": {"module_id": {"type": "string"}},
                    "required": ["module_id"],
                },
            ),
        ]

    async def handle(name: str, arguments: dict) -> list[TextContent]:
        db = get_db()

        if name == "dashboard_register_module":
            agent_id = arguments["agent_id"]
            # Check if module already exists for this agent
            existing = db.execute("SELECT id, name FROM dashboard_modules WHERE agent_id = ?", (agent_id,)).fetchone()
            if existing:
                return [TextContent(type="text", text=json.dumps({
                    "module_id": existing["id"],
                    "name": existing["name"],
                    "already_registered": True,
                }))]

            mid = str(uuid.uuid4())[:8]
            db.execute(
                "INSERT INTO dashboard_modules (id, agent_id, name, icon) VALUES (?, ?, ?, ?)",
                (mid, agent_id, arguments["name"], arguments.get("icon", "📊")),
            )
            db.commit()
            return [TextContent(type="text", text=json.dumps({
                "module_id": mid,
                "agent_id": agent_id,
                "name": arguments["name"],
                "status": "registered",
            }))]

        elif name == "dashboard_list_modules":
            rows = db.execute("SELECT * FROM dashboard_modules ORDER BY created_at").fetchall()
            modules = []
            for r in rows:
                widget_count = db.execute("SELECT COUNT(*) as cnt FROM dashboard_widgets WHERE module_id = ?", (r["id"],)).fetchone()["cnt"]
                modules.append({**dict(r), "widget_count": widget_count})
            return [TextContent(type="text", text=json.dumps({"modules": modules, "count": len(modules)}))]

        elif name == "dashboard_remove_module":
            mid = arguments["module_id"]
            db.execute("DELETE FROM dashboard_widgets WHERE module_id = ?", (mid,))
            db.execute("DELETE FROM dashboard_modules WHERE id = ?", (mid,))
            db.commit()
            return [TextContent(type="text", text=json.dumps({"deleted": mid}))]

        raise ValueError(f"Unknown tool: {name}")

    return _tools, handle
