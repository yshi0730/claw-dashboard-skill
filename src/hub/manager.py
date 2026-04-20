"""Hub process manager — start, stop, status for hub and cloudflared."""

from __future__ import annotations

import json
import logging
import os
import signal
import subprocess
from pathlib import Path
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

CLAW_DIR = Path.home() / ".claw"
HUB_DIR = CLAW_DIR / "hub"
CONFIG_DIR = CLAW_DIR / "config"
PID_DIR = CLAW_DIR / "run"


def _pid_file(name: str) -> Path:
    PID_DIR.mkdir(parents=True, exist_ok=True)
    return PID_DIR / f"{name}.pid"


def _is_process_running(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except (OSError, ProcessLookupError):
        return False


def _read_pid(name: str) -> Optional[int]:
    pf = _pid_file(name)
    if pf.exists():
        try:
            pid = int(pf.read_text().strip())
            if _is_process_running(pid):
                return pid
            pf.unlink()
        except (ValueError, OSError):
            pass
    return None


def _write_pid(name: str, pid: int):
    _pid_file(name).write_text(str(pid))


def is_hub_running() -> bool:
    return _read_pid("hub") is not None


def is_tunnel_running() -> bool:
    return _read_pid("cloudflared") is not None


def start_hub(port: int = 3000) -> dict:
    """Start the dashboard hub web server."""
    existing = _read_pid("hub")
    if existing:
        return {"status": "already_running", "pid": existing, "port": port}

    app_file = HUB_DIR / "app.py"
    if not app_file.exists():
        return {"status": "error", "message": "Hub not installed. Run dashboard_setup first."}

    proc = subprocess.Popen(
        ["python3", "-m", "uvicorn", "app:app", "--host", "0.0.0.0", "--port", str(port)],
        cwd=str(HUB_DIR),
        stdout=open(CLAW_DIR / "hub.log", "a"),
        stderr=subprocess.STDOUT,
        start_new_session=True,
    )
    _write_pid("hub", proc.pid)
    return {"status": "started", "pid": proc.pid, "port": port}


def stop_hub() -> dict:
    pid = _read_pid("hub")
    if not pid:
        return {"status": "not_running"}
    try:
        os.kill(pid, signal.SIGTERM)
        _pid_file("hub").unlink(missing_ok=True)
        return {"status": "stopped", "pid": pid}
    except OSError as e:
        return {"status": "error", "message": str(e)}


def start_tunnel() -> dict:
    """Start cloudflared tunnel using saved config."""
    existing = _read_pid("cloudflared")
    if existing:
        return {"status": "already_running", "pid": existing}

    config_file = CONFIG_DIR / "tunnel.json"
    if not config_file.exists():
        return {"status": "error", "message": "Tunnel not configured. Run dashboard_setup first."}

    config = json.loads(config_file.read_text())
    tunnel_token = config.get("tunnel_token")
    if not tunnel_token:
        return {"status": "error", "message": "No tunnel token in config"}

    from .installer import get_cloudflared_path
    cloudflared = get_cloudflared_path()

    proc = subprocess.Popen(
        [cloudflared, "tunnel", "run", "--token", tunnel_token],
        stdout=open(CLAW_DIR / "tunnel.log", "a"),
        stderr=subprocess.STDOUT,
        start_new_session=True,
    )
    _write_pid("cloudflared", proc.pid)
    return {"status": "started", "pid": proc.pid}


def stop_tunnel() -> dict:
    pid = _read_pid("cloudflared")
    if not pid:
        return {"status": "not_running"}
    try:
        os.kill(pid, signal.SIGTERM)
        _pid_file("cloudflared").unlink(missing_ok=True)
        return {"status": "stopped", "pid": pid}
    except OSError as e:
        return {"status": "error", "message": str(e)}


def get_status() -> dict:
    """Get full dashboard status."""
    hub_pid = _read_pid("hub")
    tunnel_pid = _read_pid("cloudflared")

    config_file = CONFIG_DIR / "tunnel.json"
    public_url = None
    serial = None
    if config_file.exists():
        try:
            cfg = json.loads(config_file.read_text())
            public_url = cfg.get("public_url")
            serial = cfg.get("serial")
        except Exception:
            pass

    # Check hub health
    hub_healthy = False
    if hub_pid:
        try:
            resp = httpx.get("http://localhost:3000/api/health", timeout=3)
            hub_healthy = resp.status_code == 200
        except Exception:
            pass

    return {
        "hub": {
            "installed": (HUB_DIR / "app.py").exists(),
            "running": hub_pid is not None,
            "pid": hub_pid,
            "healthy": hub_healthy,
            "local_url": "http://localhost:3000" if hub_pid else None,
        },
        "tunnel": {
            "running": tunnel_pid is not None,
            "pid": tunnel_pid,
            "public_url": public_url if tunnel_pid else None,
        },
        "serial": serial,
        "public_url": public_url,
    }
