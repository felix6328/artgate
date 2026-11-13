"""检索入口。

v1：结构化过滤 + OpenCLIP 语义相似（retriever="semantic"）。
v2：在 v1 语义一路之外，增加 BM25 词法一路与 RRF 融合（retriever="hybrid"，默认），
    并对 BM25 查询做手写同义词扩展。语义一路仍用原始查询，不把译名塞进 CLIP。

失败兜底：嵌入不可用时降级为 BM25（再不行才用旧的文件名重叠搜索），并明确提示。
过短或过宽的查询：仍返回结果，但带提示让用户加约束。
精确已知 ID 走元数据，不绕向量。
"""
from __future__ import annotations

import re
import time
from pathlib import Path
from typing import Any

from artgate.config import settings
from artgate.db import get_asset, list_assets
from artgate.search import embedder, index as vecindex
from artgate.search import bm25 as bm25mod
from artgate.search.expand import expand as expand_query
from artgate.search.hybrid import RRF_K, WEIGHTS, classify_query, rrf_fuse

BROAD = {
    "武器", "道具", "树", "角色", "贴图", "场景", "食物", "建筑",
    "weapon", "weapons", "food", "tree", "character", "ui", "prop", "item",
}


def is_broad_query(q: str) -> bool:
    """只对明确的过宽词提示加过滤，避免把「一把剑」这种完整短语误判为过宽。"""
    q = (q or "").strip()
    cfg = settings().get("search") or {}
    examples = set((cfg.get("broad_query_examples") or []) + list(BROAD))
    return q.lower() in {e.lower() for e in examples}


def _retriever_default() -> str:
    cfg = settings().get("search") or {}
    return str(cfg.get("retriever") or "hybrid")


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
    retriever: str | None = None,
) -> dict[str, Any]:
    t0 = time.perf_counter()
    warnings: list[str] = []
    retriever = (retriever or _retriever_default()).lower()
    if exact_id:
        asset = get_asset(exact_id)
        ms = (time.perf_counter() - t0) * 1000
        return {
            "mode": "exact_id",
            "retriever": retriever,
            "query": query,
            "results": [asset] if asset else [],
            "warnings": [],
            "duration_ms": round(ms, 2),
            "semantic_available": True,
        }
    if is_broad_query(query):
        warnings.append("查询较宽，建议补充类型、项目或风格等过滤条件；已返回过滤后的结果。")

    expansion = expand_query(query)
    qtype = classify_query(query)
    filt = dict(
        project_id=project_id,
        asset_type=asset_type,
        format_=format_,
        triangle_min=triangle_min,
        triangle_max=triangle_max,
        cross_project=cross_project,
    )
    cfg = settings().get("search") or {}
    cand_k = int(cfg.get("candidate_k") or 50)
    rrf_k = int(cfg.get("rrf_k") or RRF_K)
    want_expand = cfg.get("expand_for_bm25", True)
    bm25_tokens = expansion.bm25_tokens if want_expand else expansion.original_tokens

    # --- 词法一路（总是算，失败降级和基线都用得上；hybrid / bm25 需要） ---
    bm25_hits: list[dict[str, Any]] = []
    if retriever in ("hybrid", "bm25", "lexical"):
        try:
            idx = bm25mod.get_index()
            bm25_hits = idx.search(bm25_tokens, top_k=max(cand_k, top_k), **filt)
        except Exception as e:
            warnings.append(f"BM25 不可用: {type(e).__name__}: {e}")

    # --- 仅 BM25 ---
    if retriever in ("bm25", "lexical"):
        results = [_enrich(h) for h in bm25_hits[:top_k]]
        ms = (time.perf_counter() - t0) * 1000
        return _pack(
            mode="bm25",
            retriever=retriever,
            query=query,
            results=results,
            warnings=warnings,
            duration_ms=ms,
            semantic_available=False,
            project_id=project_id,
            cross_project=cross_project,
            filters=filt,
            expansion=expansion.as_dict(),
            query_type=qtype,
            top_k=top_k,
        )

    # --- 语义一路 ---
    ok, err = True, ""
    try:
        vec = embedder.embed_texts([query])[0]
    except Exception as e:
        ok, err = False, f"{type(e).__name__}: {e}"
        vec = None

    sem_hits: list[dict[str, Any]] = []
    if ok and vec is not None:
        try:
            fetch_k = max(cand_k, top_k) if retriever == "hybrid" else top_k
            sem_hits = vecindex.search_vectors(vec, top_k=fetch_k, **filt)
        except Exception as e:
            ok, err = False, f"{type(e).__name__}: {e}"

    if not ok or vec is None:
        # 降级：有 BM25 用 BM25，否则用旧文件名重叠
        if bm25_hits:
            results = [_enrich(h) for h in bm25_hits[:top_k]]
            mode = "bm25_fallback"
        else:
            results = metadata_search(query, top_k=top_k, **filt)
            mode = "metadata_fallback"
        warnings.append("语义检索暂时不可用，已降级为词法搜索。")
        if err:
            warnings.append(err)
        ms = (time.perf_counter() - t0) * 1000
        return _pack(
            mode=mode,
            retriever=retriever,
            query=query,
            results=results,
            warnings=warnings,
            duration_ms=ms,
            semantic_available=False,
            project_id=project_id,
            cross_project=cross_project,
            filters=filt,
            expansion=expansion.as_dict(),
            query_type=qtype,
            top_k=top_k,
        )

    if retriever == "semantic":
        results = [_enrich(h) for h in sem_hits[:top_k]]
        ms = (time.perf_counter() - t0) * 1000
        if not results and (asset_type or format_ or triangle_min is not None or triangle_max is not None):
            warnings.append("过滤后结果为空。可放宽类型、格式或面数区间。")
        return _pack(
            mode="semantic",
            retriever="semantic",
            query=query,
            results=results,
            warnings=warnings,
            duration_ms=ms,
            semantic_available=True,
            project_id=project_id,
            cross_project=cross_project,
            filters=filt,
            expansion=expansion.as_dict(),
            query_type=qtype,
            top_k=top_k,
        )

    # --- hybrid：RRF ---
    if cfg.get("router_enabled", True):
        weights = dict(WEIGHTS.get(qtype) or WEIGHTS["descriptive"])
        rw = (cfg.get("router_weights") or {}).get(qtype)
        if isinstance(rw, dict) and rw:
            weights = {**weights, **{k: float(v) for k, v in rw.items()}}
    else:
        weights = dict(WEIGHTS["descriptive"])
    fused = rrf_fuse(
        {"semantic": sem_hits, "bm25": bm25_hits},
        weights=weights,
        k=rrf_k,
        top_k=top_k,
    )
    results = [_enrich(h) for h in fused]
    if not results and (asset_type or format_ or triangle_min is not None or triangle_max is not None):
        warnings.append("过滤后结果为空。可放宽类型、格式或面数区间。")
    if expansion.added_terms:
        warnings.append(
            "词法一路已用同义词扩展：" + "、".join(expansion.matched_terms)
            + " → " + ", ".join(expansion.added_terms)
        )
    ms = (time.perf_counter() - t0) * 1000
    return _pack(
        mode="hybrid",
        retriever="hybrid",
        query=query,
        results=results,
        warnings=warnings,
        duration_ms=ms,
        semantic_available=True,
        project_id=project_id,
        cross_project=cross_project,
        filters=filt,
        expansion=expansion.as_dict(),
        query_type=qtype,
        fusion={"method": "rrf", "k": rrf_k, "weights": weights, "candidate_k": cand_k},
        top_k=top_k,
    )


def _pack(**kwargs) -> dict[str, Any]:
    filt = kwargs.get("filters") or {}
    kwargs["filters"] = {
        "asset_type": filt.get("asset_type"),
        "format": filt.get("format_"),
        "triangle_min": filt.get("triangle_min"),
        "triangle_max": filt.get("triangle_max"),
    }
    return kwargs


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
    """以图搜图仍走纯语义（查询不是文本，BM25 与同义词不适用）。"""
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
    """文件名 / 标签 / 描述的词项重叠排序，作为 v1 文件名基线与最终降级路径。不改逻辑，保证与 v1 对比公平。"""
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
    """v1 文件名基线用的分词，保持原样。"""
    q = (q or "").lower().strip()
    en = re.findall(r"[a-z0-9]+", q)
    zh = re.findall(r"[\u4e00-\u9fff]+", q)
    tokens = list(en)
    for z in zh:
        tokens.append(z)
        if len(z) >= 2:
            tokens.extend(z[i : i + 2] for i in range(len(z) - 1))
    stop = {"的", "一个", "一把", "一种", "一些", "a", "an", "the", "of", "and"}
    return [t for t in tokens if t not in stop and len(t) >= 1]


def _enrich(hit: dict[str, Any]) -> dict[str, Any]:
    aid = hit.get("asset_id") or hit.get("id")
    if aid:
        full = get_asset(aid)
        if full:
            merged = dict(full)
            merged["score"] = hit.get("score")
            merged["_distance"] = hit.get("_distance")
            if hit.get("rrf") is not None:
                merged["rrf"] = hit["rrf"]
            if hit.get("component_ranks"):
                merged["component_ranks"] = hit["component_ranks"]
            if hit.get("component_scores"):
                merged["component_scores"] = hit["component_scores"]
            merged["mode"] = hit.get("mode") or merged.get("mode")
            return merged
    return hit
