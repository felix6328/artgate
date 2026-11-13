"""人工确认队列：通过 / 退回 / 申诉通过。改判原因必填，进入评测回流。

通过或申诉通过后才写入可检索库。禁止自动驳回 warn 项、禁止自动删除。
"""
from __future__ import annotations

from typing import Any

from artgate.db import add_review, get_asset, list_assets, latest_report, set_status
from artgate.search import embedder, index as vecindex


ALLOWED = {"pass": "approved", "reject": "rejected", "appeal_pass": "appeal_passed"}
# 对外中文动作名
ACTION_CN = {"pass": "通过", "reject": "退回", "appeal_pass": "申诉通过"}


def pending(project_id: str | None = None) -> list[dict[str, Any]]:
    rows = list_assets(project_id=project_id, status="pending")
    # 也列出 warn 等待确认的（我们用 pending 统一）
    out = []
    for r in rows:
        report = latest_report(r["id"])
        item = dict(r)
        item["latest_report"] = report
        out.append(item)
    return out


def apply_review(
    asset_id: str,
    action: str,
    reason: str,
    reviewer: str = "TA",
) -> dict[str, Any]:
    if action not in ALLOWED:
        raise ValueError(f"未知动作 {action}，应为 pass / reject / appeal_pass")
    if not (reason or "").strip():
        raise ValueError("改判或确认原因必填，这是回流评测的输入。")
    asset = get_asset(asset_id)
    if not asset:
        raise KeyError(f"资产不存在: {asset_id}")
    prev = asset.get("status") or "pending"
    new = ALLOWED[action]
    set_status(asset_id, new)
    add_review(asset_id, action, reason.strip(), reviewer, prev, new)
    asset = get_asset(asset_id)
    if new in ("approved", "appeal_passed"):
        _index_if_possible(asset)
    elif new == "rejected":
        try:
            vecindex.remove_vector(asset_id)
        except Exception:
            pass
    return {"ok": True, "asset": asset, "action": action, "new_status": new}


def _index_if_possible(asset: dict[str, Any]) -> None:
    preview = asset.get("preview_path")
    if not preview:
        return
    from pathlib import Path

    p = Path(preview)
    if not p.exists():
        return
    try:
        vec = embedder.embed_images([p])[0]
        dim = len(vec)
        vecindex.upsert_vectors(
            [{
                "asset_id": asset["id"],
                "vector": vec,
                "project_id": asset.get("project_id"),
                "asset_type": asset.get("asset_type"),
                "format": asset.get("format"),
                "triangles": asset.get("triangles") or 0,
                "canonical_name": asset.get("canonical_name"),
                "original_filename": asset.get("original_filename"),
                "tags": asset.get("tags") or [],
                "description": asset.get("description") or "",
                "preview_path": asset.get("preview_path"),
                "source": asset.get("source"),
                "license": asset.get("license"),
                "status": asset.get("status"),
            }],
            dim=dim,
        )
    except Exception as e:
        # 嵌入失败不阻断确认，但资产暂不可语义检索
        add_review(asset["id"], "index_failed", f"确认已记录，但索引失败: {e}", "system", asset.get("status"), asset.get("status"))
