"""检索入口：结构化过滤 + 语义相似。精确已知 ID / 路径时走元数据，不绕向量。

失败兜底：嵌入服务不可用时降级为纯元数据（文件名 / 标签 / 类型）搜索，
并明确提示「语义检索暂时不可用」。
过短或过宽的查询：仍返回结果，但带提示让用户加约束。
"""
from __future__ import annotations

import re
import time
from pathlib import Path
from typing import Any

import numpy as np

from artgate.config import settings
from artgate.db import get_asset, list_assets
from artgate.search import embedder, index as vecindex

BROAD = {
    "武器", "道具", "树", "角色", "贴图", "场景", "食物", "建筑",
    "weapon", "weapons", "food", "tree", "character", "ui", "prop", "item",
}


def is_broad_query(q: str) -> bool:
    """只对明确的过宽词（「武器」「food」等）提示加过滤，避免把「一把剑」这种完整短语误判为过宽。"""
    q = (q or "").strip()
    cfg = settings().get("search") or {}
    examples = set((cfg.get("broad_query_examples") or []) + list(BROAD))
    return q.lower() in {e.lower() for e in examples}


def search_text(
    query: str,
    *,
    project_id: str | None,
    asset_type: str | None = None,
    format_: str | None = None,
    triangle_min: int | None = None,
    triangle_max: int | None = None,
    cross_project: bool = False,
    top_k: int = 10,
    exact_id: str | None = None,
) -> dict[str, Any]:
    t0 = time.perf_counter()
    warnings: list[str] = []
    if exact_id:
        asset = get_asset(exact_id)
        ms = (time.perf_counter() - t0) * 1000
        return {
            "mode": "exact_id",
            "query": query,
            "results": [asset] if asset else [],
            "warnings": [],
            "duration_ms": round(ms, 2),
            "semantic_available": True,
        }
    if is_broad_query(query):
        warnings.append("查询较宽，建议补充类型、项目或风格等过滤条件；已返回过滤后的语义结果。")

    ok, err = True, ""
    try:
        vec = embedder.embed_texts([query])[0]
    except Exception as e:
        ok, err = False, f"{type(e).__name__}: {e}"
        vec = None

    if not ok or vec is None:
        results = metadata_search(
            query,
            project_id=project_id,
            asset_type=asset_type,
            format_=format_,
            triangle_min=triangle_min,
            triangle_max=triangle_max,
            cross_project=cross_project,
            top_k=top_k,
        )
        ms = (time.perf_counter() - t0) * 1000
        warnings.append("语义检索暂时不可用，已降级为文件名 / 标签 / 类型搜索。")
        if err:
            warnings.append(err)
        return {
            "mode": "metadata_fallback",
            "query": query,
            "results": results,
            "warnings": warnings,
            "duration_ms": round(ms, 2),
            "semantic_available": False,
        }

    hits = vecindex.search_vectors(
        vec,
        project_id=project_id,
        asset_type=asset_type,
        format_=format_,
        triangle_min=triangle_min,
        triangle_max=triangle_max,
        cross_project=cross_project,
        top_k=top_k,
    )
    results = [_enrich(h) for h in hits]
    ms = (time.perf_counter() - t0) * 1000
    if not results and (asset_type or format_ or triangle_min is not None or triangle_max is not None):
        warnings.append("过滤后结果为空。可放宽类型、格式或面数区间。")
    return {
        "mode": "semantic",
        "query": query,
        "results": results,
        "warnings": warnings,
        "duration_ms": round(ms, 2),
        "semantic_available": True,
        "project_id": project_id,
        "cross_project": cross_project,
        "filters": {
            "asset_type": asset_type,
            "format": format_,
            "triangle_min": triangle_min,
            "triangle_max": triangle_max,
        },
    }


def search_image(
    image_path: Path,
    *,
    project_id: str | None,
    asset_type: str | None = None,
    format_: str | None = None,
    triangle_min: int | None = None,
    triangle_max: int | None = None,
    cross_project: bool = False,
    top_k: int = 10,
) -> dict[str, Any]:
    t0 = time.perf_counter()
    warnings: list[str] = []
    try:
        vec = embedder.embed_images([Path(image_path)])[0]
    except Exception as e:
        ms = (time.perf_counter() - t0) * 1000
        return {
            "mode": "metadata_fallback",
            "query": str(image_path),
            "results": [],
            "warnings": [f"语义检索暂时不可用: {type(e).__name__}: {e}"],
            "duration_ms": round(ms, 2),
            "semantic_available": False,
        }
    hits = vecindex.search_vectors(
        vec,
        project_id=project_id,
        asset_type=asset_type,
        format_=format_,
        triangle_min=triangle_min,
        triangle_max=triangle_max,
        cross_project=cross_project,
        top_k=top_k,
    )
    ms = (time.perf_counter() - t0) * 1000
    return {
        "mode": "image",
        "query": str(image_path),
        "results": [_enrich(h) for h in hits],
        "warnings": warnings,
        "duration_ms": round(ms, 2),
        "semantic_available": True,
        "project_id": project_id,
        "cross_project": cross_project,
    }


def metadata_search(
    query: str,
    *,
    project_id: str | None,
    asset_type: str | None = None,
    format_: str | None = None,
    triangle_min: int | None = None,
    triangle_max: int | None = None,
    cross_project: bool = False,
    top_k: int = 10,
    corpus: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """文件名 / 标签 / 描述的词项重叠排序，作为基线与降级路径。"""
    tokens = _tokens(query)
    assets = corpus if corpus is not None else list_assets(
        project_id=None if cross_project else project_id,
        status="approved",
        asset_type=asset_type,
    )
    scored = []
    for a in assets:
        if not cross_project and project_id and a.get("project_id") != project_id:
            continue
        if asset_type and a.get("asset_type") != asset_type:
            continue
        if format_ and a.get("format") != format_:
            continue
        tris = a.get("triangles") or 0
        if triangle_min is not None and tris < triangle_min:
            continue
        if triangle_max is not None and tris > triangle_max:
            continue
        if a.get("status") not in ("approved", "appeal_passed"):
            continue
        blob = " ".join(
            str(x) for x in [
                a.get("canonical_name"),
                a.get("original_filename"),
                a.get("description"),
                a.get("tags"),
                a.get("asset_type"),
                a.get("source_pack"),
            ] if x
        ).lower()
        score = 0.0
        for t in tokens:
            if t in blob:
                score += 1.0
                # 完整词更靠前
                if re.search(r"(^|[^a-z0-9])" + re.escape(t) + r"([^a-z0-9]|$)", blob):
                    score += 0.5
        if score > 0:
            b = dict(a)
            b["score"] = score
            b["mode"] = "filename"
            scored.append(b)
    scored.sort(key=lambda x: x["score"], reverse=True)
    return scored[:top_k]


def _tokens(q: str) -> list[str]:
    q = (q or "").lower().strip()
    # 中文按连续字、英文按词
    en = re.findall(r"[a-z0-9]+", q)
    zh = re.findall(r"[\u4e00-\u9fff]+", q)
    tokens = list(en)
    for z in zh:
        tokens.append(z)
        if len(z) >= 2:
            tokens.extend(z[i : i + 2] for i in range(len(z) - 1))
    # 去停用
    stop = {"的", "一个", "一把", "一种", "一些", "a", "an", "the", "of", "and"}
    return [t for t in tokens if t not in stop and len(t) >= 1]


def _enrich(hit: dict[str, Any]) -> dict[str, Any]:
    aid = hit.get("asset_id")
    if aid:
        full = get_asset(aid)
        if full:
            merged = dict(full)
            merged["score"] = hit.get("score")
            merged["_distance"] = hit.get("_distance")
            return merged
    return hit
