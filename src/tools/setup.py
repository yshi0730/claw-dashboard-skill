"""Setup and status tools."""

from __future__ import annotations

import json
from mcp.server import Server
from mcp.types import Tool, TextContent

from ..hub import installer, manager


def register_setup_tools(server: Server):

    def _tools() -> list[Tool]:
        return [
            Tool(
                name="dashboard_setup",
                description="Set up the dashboard hub: install hub + cloudflared, register device, start services. One-time setup, idempotent.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "serial": {"type": "string", "description": "Device serial number (12 chars). Auto-detected if omitted on ClawOS."},
                    },
                },
            ),
            Tool(
                name="dashboard_status",
                description="Check dashboard hub status: is it installed, running, tunnel active, and what's the public URL",
                inputSchema={"type": "object", "properties": {}},
            ),
            Tool(
                name="dashboard_restart",
                description="Restart dashboard hub and tunnel services",
                inputSchema={"type": "object", "properties": {}},
            ),
            Tool(
                name="dashboard_get_url",
                description="Get the public dashboard URL for the user",
                inputSchema={"type": "object", "properties": {}},
            ),
        ]

    async def handle(name: str, arguments: dict) -> list[TextContent]:

        if name == "dashboard_setup":
            steps = []

            # Step 1: Install hub
            if not installer.is_hub_installed():
                result = installer.install_hub()
                steps.append({"step": "install_hub", "result": result})
            else:
                steps.append({"step": "install_hub", "result": "already installed"})

            # Step 2: Install cloudflared
            if not installer.is_cloudflared_installed():
                result = installer.install_cloudflared()
                steps.append({"step": "install_cloudflared", "result": result})
            else:
                steps.append({"step": "install_cloudflared", "result": "already installed"})

            # Step 3: Register device
            if not installer.is_tunnel_configured():
                serial = arguments.get("serial")
                if not serial:
                    try:
                        serial = installer.get_device_serial()
                    except RuntimeError as e:
                        return [TextContent(type="text", text=json.dumps({
                            "status": "need_serial",
                            "message": str(e),
                            "steps": steps,
                        }))]
                data = installer.register_device(serial)
                steps.append({"step": "register_device", "result": "registered", "public_url": data.get("public_url")})
            else:
                config = installer.get_tunnel_config()
                steps.append({"step": "register_device", "result": "already registered", "public_url": config.get("public_url")})

            # Step 4: Start hub
            hub_result = manager.start_hub()
            steps.append({"step": "start_hub", "result": hub_result})

            # Step 5: Start tunnel
            tunnel_result = manager.start_tunnel()
            steps.append({"step": "start_tunnel", "result": tunnel_result})

            config = installer.get_tunnel_config()
            return [TextContent(type="text", text=json.dumps({
                "status": "ready",
                "public_url": config.get("public_url"),
                "local_url": "http://localhost:3000",
                "steps": steps,
            }))]

        elif name == "dashboard_status":
            status = manager.get_status()
            return [TextContent(type="text", text=json.dumps(status))]

        elif name == "dashboard_restart":
            manager.stop_tunnel()
            manager.stop_hub()
            hub = manager.start_hub()
            tunnel = manager.start_tunnel()
            config = installer.get_tunnel_config()
            return [TextContent(type="text", text=json.dumps({
                "hub": hub,
                "tunnel": tunnel,
                "public_url": config.get("public_url"),
            }))]

        elif name == "dashboard_get_url":
            config = installer.get_tunnel_config()
            url = config.get("public_url")
            if url:
                return [TextContent(type="text", text=json.dumps({"public_url": url, "local_url": "http://localhost:3000"}))]
            return [TextContent(type="text", text=json.dumps({"error": "Dashboard not set up yet. Run dashboard_setup first."}))]

        raise ValueError(f"Unknown tool: {name}")

    return _tools, handle
