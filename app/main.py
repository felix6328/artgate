"""ArtGate 工作台：FastAPI + 单页界面。"""
from __future__ import annotations

import sys
from pathlib import Path

# 保证以 python app/main.py 或 uvicorn app.main:app 都能 import artgate
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import json
import tempfile
from typing import Optional

from fastapi import FastAPI, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from artgate.config import list_projects, load_template, settings
from artgate.db import cost_summary, get_asset, init_schema, latest_report, list_assets, list_reviews
from artgate.ingest.importer import ingest_file
from artgate.paths import DATA, PREVIEWS, REPO_ROOT, ensure_dirs
from artgate.review.queue import apply_review, pending
from artgate.search.query import search_image, search_text
from artgate.search import index as vecindex

ensure_dirs()
init_schema()

app = FastAPI(title="ArtGate", version="0.1.0", description="游戏美术资产语义检索与入库预检工作台")
STATIC = Path(__file__).resolve().parent / "static"
TEMPLATES = Path(__file__).resolve().parent / "templates"
STATIC.mkdir(parents=True, exist_ok=True)
app.mount("/static", StaticFiles(directory=str(STATIC)), name="static")


@app.get("/", response_class=HTMLResponse)
def home():
    html = (TEMPLATES / "index.html").read_text(encoding="utf-8")
    return HTMLResponse(html)


@app.get("/api/health")
def health():
    return {
        "ok": True,
        "projects": list_projects(),
        "indexed": vecindex.count_indexed() if vecindex.has_table() else 0,
        "embedder": settings()["embedder"],
        "vlm": {k: v for k, v in (settings().get("vlm") or {}).items() if k != "api_key"},
    }


@app.get("/api/templates")
def templates():
    out = []
    for pid in list_projects():
        t = load_template(pid)
        # 不把可能很大的无关字段去掉
        out.append(t)
    return {"projects": out}


@app.get("/api/search")
def api_search(
    q: str = Query(..., min_length=1),
    project_id: Optional[str] = None,
    asset_type: Optional[str] = None,
    format: Optional[str] = None,
    triangle_min: Optional[int] = None,
    triangle_max: Optional[int] = None,
    cross_project: bool = False,
    top_k: int = 10,
    exact_id: Optional[str] = None,
):
    return search_text(
        q,
        project_id=project_id,
        asset_type=asset_type,
        format_=format,
        triangle_min=triangle_min,
        triangle_max=triangle_max,
        cross_project=cross_project,
        top_k=top_k,
        exact_id=exact_id,
    )


@app.post("/api/search/image")
async def api_search_image(
    file: UploadFile = File(...),
    project_id: Optional[str] = Form(None),
    asset_type: Optional[str] = Form(None),
    format: Optional[str] = Form(None),
    triangle_min: Optional[int] = Form(None),
    triangle_max: Optional[int] = Form(None),
    cross_project: bool = Form(False),
    top_k: int = Form(10),
):
    suffix = Path(file.filename or "query.png").suffix or ".png"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(await file.read())
        tmp_path = Path(tmp.name)
    try:
        return search_image(
            tmp_path,
            project_id=project_id,
            asset_type=asset_type,
            format_=format,
            triangle_min=triangle_min,
            triangle_max=triangle_max,
            cross_project=cross_project,
            top_k=top_k,
        )
    finally:
        tmp_path.unlink(missing_ok=True)


@app.post("/api/ingest")
async def api_ingest(
    file: UploadFile = File(...),
    project_id: str = Form(...),
    asset_type: str = Form("prop"),
    skip_vlm: bool = Form(False),
    vlm_backend: Optional[str] = Form(None),
):
    if project_id not in list_projects():
        raise HTTPException(400, f"未知项目 {project_id}")
    suffix = Path(file.filename or "upload.bin").suffix
    dest_dir = DATA / "incoming" / project_id
    dest_dir.mkdir(parents=True, exist_ok=True)
    raw = dest_dir / (file.filename or "upload.bin")
    raw.write_bytes(await file.read())
    result = ingest_file(
        raw,
        project_id,
        asset_type=asset_type,
        source="upload",
        original_filename=file.filename,
        copy=False,
        skip_vlm=skip_vlm,
        vlm_backend=vlm_backend,
        uploader="web",
    )
    return result


@app.get("/api/queue")
def api_queue(project_id: Optional[str] = None):
    return {"items": pending(project_id)}


@app.post("/api/queue/{asset_id}/review")
def api_review(asset_id: str, payload: dict):
    action = payload.get("action")
    reason = payload.get("reason") or ""
    reviewer = payload.get("reviewer") or "TA"
    try:
        return apply_review(asset_id, action, reason, reviewer)
    except ValueError as e:
        raise HTTPException(400, str(e))
    except KeyError as e:
        raise HTTPException(404, str(e))


@app.get("/api/assets")
def api_assets(project_id: Optional[str] = None, status: Optional[str] = None, asset_type: Optional[str] = None):
    return {"items": list_assets(project_id=project_id, status=status, asset_type=asset_type)}


@app.get("/api/assets/{asset_id:path}")
def api_asset(asset_id: str):
    a = get_asset(asset_id)
    if not a:
        raise HTTPException(404, "资产不存在")
    a["latest_report"] = latest_report(asset_id)
    a["reviews"] = list_reviews(asset_id)
    return a


@app.get("/api/cost")
def api_cost():
    return cost_summary()


@app.get("/api/eval")
def api_eval():
    p = REPO_ROOT / "eval" / "results.md"
    if not p.exists():
        return {"exists": False, "text": "尚未运行评测。请执行 python scripts/run_eval.py"}
    return {"exists": True, "text": p.read_text(encoding="utf-8")}


@app.get("/previews/{name}")
def serve_preview(name: str):
    # 仅允许预览目录内的文件名
    p = PREVIEWS / Path(name).name
    if not p.exists():
        # 也允许用 asset_id 转换
        alt = PREVIEWS / name
        if alt.exists():
            p = alt
        else:
            raise HTTPException(404)
    return FileResponse(p)


@app.get("/api/preview")
def api_preview(path: str):
    """按预览绝对/相对路径取图，限制在仓库 data/ 下。"""
    p = Path(path)
    if not p.is_absolute():
        p = (REPO_ROOT / p).resolve()
    else:
        p = p.resolve()
    allowed = (DATA.resolve(), PREVIEWS.resolve())
    if not any(str(p).startswith(str(a)) for a in allowed):
        raise HTTPException(403, "路径不允许")
    if not p.exists():
        raise HTTPException(404)
    return FileResponse(p)


def preview_url(asset: dict) -> str:
    pp = asset.get("preview_path") or ""
    if not pp:
        return ""
    name = Path(pp).name
    if (PREVIEWS / name).exists():
        return f"/previews/{name}"
    return f"/api/preview?path={pp}"


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="127.0.0.1", port=8765, reload=False)
