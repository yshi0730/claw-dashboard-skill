"""Dashboard Hub — FastAPI web server serving the dashboard UI."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

app = FastAPI(title="Claw Dashboard Hub")

CLAW_DIR = Path.home() / ".claw"
DB_PATH = CLAW_DIR / "shared" / "shared.db"
STATIC_DIR = Path(__file__).parent / "public"
TEMPLATES_DIR = Path(__file__).parent / "templates"

templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


def get_db() -> sqlite3.Connection:
    db = sqlite3.connect(str(DB_PATH))
    db.row_factory = sqlite3.Row
    return db


# ── API endpoints ──

@app.get("/api/health")
async def health():
    return {"status": "ok", "version": "0.1.0"}


@app.get("/api/modules")
async def list_modules():
    db = get_db()
    rows = db.execute("SELECT * FROM dashboard_modules ORDER BY created_at").fetchall()
    modules = []
    for r in rows:
        wc = db.execute("SELECT COUNT(*) as cnt FROM dashboard_widgets WHERE module_id = ?", (r["id"],)).fetchone()["cnt"]
        modules.append({**dict(r), "widget_count": wc})
    db.close()
    return {"modules": modules}


@app.get("/api/modules/{module_id}/widgets")
async def get_widgets(module_id: str):
    db = get_db()
    rows = db.execute(
        "SELECT * FROM dashboard_widgets WHERE module_id = ? ORDER BY position", (module_id,)
    ).fetchall()
    widgets = []
    for r in rows:
        w = dict(r)
        w["config"] = json.loads(w["config"])
        w["data"] = json.loads(w["data"])
        widgets.append(w)
    db.close()
    return {"widgets": widgets}


@app.get("/api/kv/{namespace}/{key}")
async def get_kv(namespace: str, key: str):
    db = get_db()
    row = db.execute(
        "SELECT value, updated_at FROM dashboard_kv WHERE namespace = ? AND key = ?", (namespace, key)
    ).fetchone()
    db.close()
    if not row:
        return JSONResponse({"error": "not_found"}, 404)
    return {"namespace": namespace, "key": key, "value": json.loads(row["value"]), "updated_at": row["updated_at"]}


# ── HTML pages ──

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    db = get_db()
    modules = db.execute("SELECT * FROM dashboard_modules ORDER BY created_at").fetchall()
    modules = [dict(m) for m in modules]
    db.close()
    return templates.TemplateResponse("index.html", {"request": request, "modules": modules})


@app.get("/m/{module_id}", response_class=HTMLResponse)
async def module_page(request: Request, module_id: str):
    db = get_db()
    module = db.execute("SELECT * FROM dashboard_modules WHERE id = ?", (module_id,)).fetchone()
    if not module:
        return HTMLResponse("<h1>Module not found</h1>", 404)
    module = dict(module)

    widgets = db.execute(
        "SELECT * FROM dashboard_widgets WHERE module_id = ? ORDER BY position", (module_id,)
    ).fetchall()
    widget_list = []
    for w in widgets:
        wd = dict(w)
        wd["config"] = json.loads(wd["config"])
        wd["data"] = json.loads(wd["data"])
        widget_list.append(wd)
    db.close()
    return templates.TemplateResponse("module.html", {
        "request": request, "module": module, "widgets": widget_list,
    })


def main():
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=3000)


if __name__ == "__main__":
    main()
