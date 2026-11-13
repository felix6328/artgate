"""混合检索：OpenCLIP 语义分 + BM25 词法分，用 RRF 融合。

为什么用 RRF 而不是加权原始分：
- CLIP 的展示分（由距离变换而来）和 BM25 的 IDF 分数量纲不同，直接加权要先归一化，
  归一化方式本身就是一组容易过拟合的超参。
- RRF 只看排序，score = Σ_i w_i / (k + rank_i)，k=60 是公开文献的常用值（Cormack et al.）。
- 本版 k 与默认权重在看本轮 dev/test 数字之前冻结；查询类型路由只改变权重，不改 k。

查询类型路由（先验，来自 v1 已发布的观察：英文短查询常与英文文件名重叠）：
- filename_like：标识符、路径、或 1–2 个英文实词（如 "a sword"、"pistol"）→ 略抬 BM25
- descriptive：含中文，或更长的英文描述 → 两路等权（扩展后的 BM25 仍然在）
"""
from __future__ import annotations

import re
from collections import defaultdict
from typing import Any

from artgate.search.tokenize import STOP, tokenize

RRF_K = 60
WEIGHTS = {
    "filename_like": {"semantic": 1.0, "bm25": 1.5},
    "descriptive": {"semantic": 1.0, "bm25": 1.0},
}

_EXT = re.compile(r"\.(glb|gltf|png|jpg|jpeg|fbx|obj|webp|ktx2)$", re.I)
_CAMEL_IDENT = re.compile(r"(?:[a-z][A-Z])")  # 必须大小写敏感；IGNORECASE 会把任意两字母当成驼峰
_PATHISH = re.compile(r"[\\/_]")


def classify_query(query: str) -> str:
    q = (query or "").strip()
    if not q:
        return "descriptive"
    if re.search(r"[\u4e00-\u9fff]", q):
        return "descriptive"
    if _PATHISH.search(q) or _CAMEL_IDENT.search(q) or _EXT.search(q):
        return "filename_like"
    words = tokenize(q)
    content = [w for w in words if w not in STOP]
    if len(content) <= 2:
        return "filename_like"
    return "descriptive"


def rrf_fuse(
    lists: dict[str, list[dict[str, Any]]],
    *,
    weights: dict[str, float],
    k: int = RRF_K,
    top_k: int = 10,
    id_keys: tuple[str, ...] = ("id", "asset_id"),
) -> list[dict[str, Any]]:
    """lists: 检索源名 → 已按该源排序的命中列表。权重缺省为 1。"""
    scores: dict[str, float] = defaultdict(float)
    ranks: dict[str, dict[str, int]] = defaultdict(dict)
    raw: dict[str, dict[str, Any]] = {}
    src_scores: dict[str, dict[str, float]] = defaultdict(dict)

    def aid(hit: dict[str, Any]) -> str | None:
        for key in id_keys:
            v = hit.get(key)
            if v:
                return str(v)
        return None

    for src, hits in lists.items():
        w = float(weights.get(src, 1.0))
        for rank, hit in enumerate(hits, 1):
            i = aid(hit)
            if not i:
                continue
            scores[i] += w / (k + rank)
            ranks[i][src] = rank
            src_scores[i][src] = float(hit.get("score") or 0.0)
            if i not in raw:
                raw[i] = hit

    ranked = sorted(scores.items(), key=lambda kv: (-kv[1], kv[0]))
    out = []
    for i, s in ranked[: max(top_k, 0)]:
        rec = dict(raw[i])
        rec["score"] = float(s)
        rec["rrf"] = float(s)
        rec["component_ranks"] = dict(ranks[i])
        rec["component_scores"] = dict(src_scores[i])
        rec["mode"] = "hybrid"
        rec["asset_id"] = rec.get("asset_id") or rec.get("id")
        out.append(rec)
    return out
