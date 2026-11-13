"""本地文件夹 / 上传文件接入：记哈希、原始路径、项目、类型、上传者；跑预检；入队。"""
from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from artgate.config import load_template, make_canonical
from artgate.db import get_asset, save_report, upsert_asset
from artgate.hashutil import file_sha256
from artgate.paths import DATA, PREVIEWS, ensure_dirs
from artgate.precheck.engine import run_precheck
from artgate.search.preview import make_preview, preview_path_for


def make_asset_id(project_id: str, source: str, rel: str) -> str:
    rel = rel.replace("\\", "/").lstrip("/")
    return f"{project_id}:{source}:{rel}"


def ingest_file(
    src: Path,
    project_id: str,
    *,
    asset_type: str = "prop",
    source: str = "upload",
    source_pack: str = "",
    license_name: str = "",
    tags: list[str] | None = None,
    description: str = "",
    original_filename: str | None = None,
    canonical_name: str | None = None,
    lod: int = 0,
    dest_dir: Path | None = None,
    copy: bool = True,
    preview_src: Path | None = None,
    auto_status: str | None = None,
    index: bool = True,
    skip_vlm: bool = False,
    vlm_backend: str | None = None,
    companion_files: list[Path] | None = None,
    metadata: dict[str, Any] | None = None,
    uploader: str = "local",
) -> dict[str, Any]:
    """接入单个文件。默认状态 pending，进入人工队列。

    auto_status='approved' 仅用于种子库模拟「已在生产库的历史资产」，
    仍会跑预检并写下 seed_approve 原因，不会假装没做过确认。
    """
    ensure_dirs()
    src = Path(src)
    if not src.exists():
        raise FileNotFoundError(src)
    template = load_template(project_id)
    orig = original_filename or src.name
    ext = src.suffix.lower().lstrip(".")
    canon = canonical_name or make_canonical(template, asset_type, Path(orig).stem, ext, lod=lod)
    file_hash = file_sha256(src)
    rel = orig
    asset_id = make_asset_id(project_id, source, f"{source_pack}/{orig}" if source_pack else orig)

    stored = src
    if copy:
        dest_dir = Path(dest_dir or (DATA / "incoming" / project_id))
        dest_dir.mkdir(parents=True, exist_ok=True)
        stored = dest_dir / canon
        if stored.resolve() != src.resolve():
            shutil.copy2(src, stored)

    prev = preview_path_for(asset_id)
    prev_result = make_preview(preview_src or stored, prev)

    report = run_precheck(
        stored,
        project_id,
        asset_type=asset_type,
        canonical_name=canon,
        original_filename=orig,
        tags=tags or [],
        preview_path=prev if prev.exists() else None,
        lod=lod,
        companion_files=companion_files,
        skip_vlm=skip_vlm,
        vlm_backend=vlm_backend,
        asset_id=asset_id,
        file_size=stored.stat().st_size,
    )

    triangles = None
    tex_max = None
    tools = report.get("tools") or {}
    insp = tools.get("mesh_inspect") or {}
    if insp.get("triangles") is not None:
        triangles = int(insp["triangles"])
    if insp.get("tex_max_side"):
        tex_max = int(insp["tex_max_side"])
    # 也从检查项取
    for it in report.get("items") or []:
        if it["check_id"] == "poly_budget" and isinstance(it.get("measured"), int):
            triangles = it["measured"]

    status = auto_status or "pending"
    upsert_asset({
        "id": asset_id,
        "file_hash": file_hash,
        "original_path": str(src),
        "original_filename": orig,
        "canonical_name": canon,
        "preview_path": str(prev) if prev.exists() else "",
        "project_id": project_id,
        "asset_type": asset_type,
        "format": ext,
        "triangles": triangles,
        "tex_max_side": tex_max,
        "file_size": stored.stat().st_size,
        "license": license_name,
        "source": source,
        "source_pack": source_pack,
        "tags": tags or [],
        "description": description,
        "status": status,
        "lod": lod,
        "metadata": {
            **(metadata or {}),
            "uploader": uploader,
            "preview": prev_result,
            "precheck_overall": report.get("overall"),
        },
    })
    save_report(asset_id, project_id, report.get("overall", ""), report, report.get("duration_ms") or 0)

    if index and status in ("approved", "appeal_passed"):
        from artgate.review.queue import _index_if_possible

        _index_if_possible(get_asset(asset_id))

    return {
        "asset_id": asset_id,
        "canonical_name": canon,
        "status": status,
        "report": report,
        "preview": prev_result,
        "asset": get_asset(asset_id),
    }
