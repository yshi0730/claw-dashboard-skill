"""Widget management tools — add charts, tables, KPI cards to modules."""

from __future__ import annotations

import json
import uuid
from mcp.server import Server
from mcp.types import Tool, TextContent

from ..storage.db import get_db

WIDGET_TYPES = ["kpi_card", "line_chart", "bar_chart", "pie_chart", "table", "text", "stat_row"]


def register_widget_tools(server: Server):

    def _tools() -> list[Tool]:
        return [
            Tool(
                name="dashboard_add_widget",
                description="Add a widget (chart, table, KPI card, etc.) to a dashboard module",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "module_id": {"type": "string", "description": "Module ID to add widget to"},
                        "widget_type": {"type": "string", "enum": WIDGET_TYPES, "description": "Widget type"},
                        "title": {"type": "string", "description": "Widget title"},
                        "config": {"type": "object", "description": "Widget-specific config (colors, labels, axes, etc.)"},
                        "data": {"description": "Initial data for the widget (format depends on widget_type)"},
                    },
                    "required": ["module_id", "widget_type", "title"],
                },
            ),
            Tool(
                name="dashboard_update_widget",
                description="Update a widget's data or config",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "widget_id": {"type": "string"},
                        "data": {"description": "New data for the widget"},
                        "config": {"type": "object", "description": "Updated config (merged with existing)"},
                        "title": {"type": "string", "description": "New title (optional)"},
                    },
                    "required": ["widget_id"],
                },
            ),
            Tool(
                name="dashboard_remove_widget",
                description="Remove a widget from the dashboard",
                inputSchema={
                    "type": "object",
                    "properties": {"widget_id": {"type": "string"}},
                    "required": ["widget_id"],
                },
            ),
            Tool(
                name="dashboard_list_widgets",
                description="List all widgets in a module",
                inputSchema={
                    "type": "object",
                    "properties": {"module_id": {"type": "string"}},
                    "required": ["module_id"],
                },
            ),
            Tool(
                name="dashboard_push_data",
                description="Push data to the shared key-value store. Other agents or the dashboard can read this.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "namespace": {"type": "string", "description": "Data namespace (e.g. agent ID)"},
                        "key": {"type": "string"},
                        "value": {"description": "Any JSON-serializable value"},
                    },
                    "required": ["namespace", "key", "value"],
                },
            ),
            Tool(
                name="dashboard_get_data",
                description="Read data from the shared key-value store",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "namespace": {"type": "string"},
                        "key": {"type": "string"},
                    },
                    "required": ["namespace", "key"],
                },
            ),
        ]

    async def handle(name: str, arguments: dict) -> list[TextContent]:
        db = get_db()

        if name == "dashboard_add_widget":
            wid = str(uuid.uuid4())[:8]
            # Get next position
            max_pos = db.execute(
                "SELECT COALESCE(MAX(position), -1) as mp FROM dashboard_widgets WHERE module_id = ?",
                (arguments["module_id"],),
            ).fetchone()["mp"]

            db.execute(
                "INSERT INTO dashboard_widgets (id, module_id, widget_type, title, config, data, position) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (wid, arguments["module_id"], arguments["widget_type"], arguments["title"],
                 json.dumps(arguments.get("config", {})), json.dumps(arguments.get("data", [])), max_pos + 1),
            )
            db.commit()
            return [TextContent(type="text", text=json.dumps({
                "widget_id": wid, "module_id": arguments["module_id"],
                "widget_type": arguments["widget_type"], "title": arguments["title"],
                "status": "created",
            }))]

        elif name == "dashboard_update_widget":
            wid = arguments["widget_id"]
            row = db.execute("SELECT * FROM dashboard_widgets WHERE id = ?", (wid,)).fetchone()
            if not row:
                return [TextContent(type="text", text=json.dumps({"error": "Widget not found"}))]

            updates = []
            params = []
            if "data" in arguments:
                updates.append("data = ?")
                params.append(json.dumps(arguments["data"]))
            if "config" in arguments:
                existing_config = json.loads(row["config"])
                existing_config.update(arguments["config"])
                updates.append("config = ?")
                params.append(json.dumps(existing_config))
            if "title" in arguments:
                updates.append("title = ?")
                params.append(arguments["title"])

            if updates:
                updates.append("updated_at = datetime('now')")
                params.append(wid)
                db.execute(f"UPDATE dashboard_widgets SET {', '.join(updates)} WHERE id = ?", params)
                db.commit()

            return [TextContent(type="text", text=json.dumps({"widget_id": wid, "status": "updated"}))]

        elif name == "dashboard_remove_widget":
            db.execute("DELETE FROM dashboard_widgets WHERE id = ?", (arguments["widget_id"],))
            db.commit()
            return [TextContent(type="text", text=json.dumps({"deleted": arguments["widget_id"]}))]

        elif name == "dashboard_list_widgets":
            rows = db.execute(
                "SELECT * FROM dashboard_widgets WHERE module_id = ? ORDER BY position",
                (arguments["module_id"],),
            ).fetchall()
            widgets = []
            for r in rows:
                w = dict(r)
                w["config"] = json.loads(w["config"])
                w["data"] = json.loads(w["data"])
                widgets.append(w)
            return [TextContent(type="text", text=json.dumps({"widgets": widgets, "count": len(widgets)}))]

        elif name == "dashboard_push_data":
            db.execute(
                "INSERT OR REPLACE INTO dashboard_kv (namespace, key, value, updated_at) VALUES (?, ?, ?, datetime('now'))",
                (arguments["namespace"], arguments["key"], json.dumps(arguments["value"])),
            )
            db.commit()
            return [TextContent(type="text", text=json.dumps({"namespace": arguments["namespace"], "key": arguments["key"], "status": "saved"}))]

        elif name == "dashboard_get_data":
            row = db.execute(
                "SELECT value, updated_at FROM dashboard_kv WHERE namespace = ? AND key = ?",
                (arguments["namespace"], arguments["key"]),
            ).fetchone()
            if not row:
                return [TextContent(type="text", text=json.dumps({"error": "not_found"}))]
            return [TextContent(type="text", text=json.dumps({
                "namespace": arguments["namespace"], "key": arguments["key"],
                "value": json.loads(row["value"]), "updated_at": row["updated_at"],
            }))]

        raise ValueError(f"Unknown tool: {name}")

    return _tools, handle
