"""Installer for dashboard hub and cloudflared."""

from __future__ import annotations

import logging
import os
import platform
import shutil
import stat
import subprocess
from pathlib import Path

import httpx

logger = logging.getLogger(__name__)

CLAW_DIR = Path.home() / ".claw"
HUB_DIR = CLAW_DIR / "hub"
BIN_DIR = CLAW_DIR / "bin"
CONFIG_DIR = CLAW_DIR / "config"
REGISTER_API = "https://api.clawln.app"


def is_hub_installed() -> bool:
    return (HUB_DIR / "app.py").exists()


def is_cloudflared_installed() -> bool:
    # Check our local copy first, then system
    local = BIN_DIR / "cloudflared"
    return local.exists() or shutil.which("cloudflared") is not None


def get_cloudflared_path() -> str:
    local = BIN_DIR / "cloudflared"
    if local.exists():
        return str(local)
    system = shutil.which("cloudflared")
    if system:
        return system
    raise FileNotFoundError("cloudflared not installed")


def is_tunnel_configured() -> bool:
    return (CONFIG_DIR / "tunnel.json").exists()


def get_tunnel_config() -> dict:
    import json
    config_file = CONFIG_DIR / "tunnel.json"
    if config_file.exists():
        return json.loads(config_file.read_text())
    return {}


def install_hub() -> str:
    """Install the dashboard hub app. Returns status message."""
    HUB_DIR.mkdir(parents=True, exist_ok=True)

    # Copy hub app from our package
    hub_source = Path(__file__).parent.parent.parent / "hub-app"
    if hub_source.exists():
        for f in hub_source.rglob("*"):
            if f.is_file():
                dest = HUB_DIR / f.relative_to(hub_source)
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(f, dest)
        return "Hub installed"
    return "Hub source not found — using existing installation"


def install_cloudflared() -> str:
    """Download cloudflared binary to ~/.claw/bin/."""
    BIN_DIR.mkdir(parents=True, exist_ok=True)
    target = BIN_DIR / "cloudflared"

    if target.exists():
        return "cloudflared already installed"

    system = platform.system().lower()
    machine = platform.machine().lower()

    if system == "linux":
        if machine in ("x86_64", "amd64"):
            arch = "amd64"
        elif machine in ("aarch64", "arm64"):
            arch = "arm64"
        else:
            return f"Unsupported architecture: {machine}"
        url = f"https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-{arch}"
    elif system == "darwin":
        if machine in ("arm64", "aarch64"):
            arch = "arm64"
        else:
            arch = "amd64"
        url = f"https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-darwin-{arch}.tgz"
    else:
        return f"Unsupported OS: {system}"

    logger.info(f"Downloading cloudflared from {url}")

    with httpx.Client(follow_redirects=True, timeout=120) as client:
        resp = client.get(url)
        resp.raise_for_status()

        if url.endswith(".tgz"):
            import tarfile
            import io
            tar = tarfile.open(fileobj=io.BytesIO(resp.content))
            for member in tar.getmembers():
                if member.name.endswith("cloudflared"):
                    f = tar.extractfile(member)
                    target.write_bytes(f.read())
                    break
            tar.close()
        else:
            target.write_bytes(resp.content)

    target.chmod(target.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
    return f"cloudflared installed to {target}"


def register_device(serial: str) -> dict:
    """Register device with api.clawln.app and save tunnel config."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)

    with httpx.Client(timeout=30) as client:
        resp = client.post(f"{REGISTER_API}/devices/register", json={"serial": serial})
        resp.raise_for_status()
        data = resp.json()

    if "error" in data:
        raise RuntimeError(f"Registration failed: {data['error']}")

    # Save tunnel config
    import json
    config_file = CONFIG_DIR / "tunnel.json"
    config_file.write_text(json.dumps(data, indent=2))
    config_file.chmod(0o600)

    return data


def get_device_serial() -> str:
    """Read BIOS serial number."""
    # Try dmidecode (Linux)
    try:
        result = subprocess.run(
            ["sudo", "dmidecode", "-s", "system-serial-number"],
            capture_output=True, text=True, timeout=5,
        )
        serial = result.stdout.strip()
        if serial and serial != "Default string" and len(serial) == 12:
            return serial
    except Exception:
        pass

    # Try reading from /sys (Linux, no sudo)
    try:
        serial = Path("/sys/class/dmi/id/product_serial").read_text().strip()
        if serial and serial != "Default string" and len(serial) == 12:
            return serial
    except Exception:
        pass

    # Fallback: check saved serial in config
    import json
    config_file = CONFIG_DIR / "tunnel.json"
    if config_file.exists():
        data = json.loads(config_file.read_text())
        if "serial" in data:
            return data["serial"]

    raise RuntimeError("Could not determine device serial number. Please provide it manually.")
