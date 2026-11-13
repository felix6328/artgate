"""内存 BM25 索引：文档由文件名、路径、类型、标签、描述构成。

960 条资产完全可以放内存；与向量库共用同一套结构化过滤（项目、类型、格式、面数）。
实现 Okapi / Lucene 风格 IDF：log(1 + (N - df + 0.5)/(df + 0.5))，k1=1.5，b=0.75。
不引入额外依赖，便于面试讲清楚公式。
"""
from __future__ import annotations

import math
import threading
from collections import defaultdict
from pathlib import Path
from typing import Any

from artgate.db import list_assets
from artgate.search.tokenize import tokenize

# 字段加权：用重复 token 实现。文件名和标签是美术检索最靠谱的词法信号。
FIELD_WEIGHTS = {
    "original_filename": 3,
    "stem": 2,
    "path_bits": 2,
    "source_pack": 2,
    "asset_type": 2,
    "tags": 2,
    "description": 1,
    "canonical_name": 1,
}


class BM25Index:
    def __init__(self, k1: float = 1.5, b: float = 0.75):
        self.k1 = k1
        self.b = b
        self.ids: list[str] = []
        self.docs: list[dict[str, Any]] = []
        self.tf: list[dict[str, int]] = []
        self.doc_len: list[int] = []
        self.df: dict[str, int] = {}
        self.avgdl = 0.0
        self.N = 0
        self._idf: dict[str, float] = {}

    def build(self, assets: list[dict[str, Any]]) -> None:
        self.ids = []
        self.docs = []
        self.tf = []
        self.doc_len = []
        df: dict[str, int] = defaultdict(int)
        for a in assets:
            tokens = document_tokens(a)
            if not tokens:
                # 仍入索引，避免漏掉无文件名的异常记录
                tokens = ["__empty__"]
            freq: dict[str, int] = defaultdict(int)
            for t in tokens:
                freq[t] += 1
            self.ids.append(a["id"])
            self.docs.append(a)
            self.tf.append(dict(freq))
            self.doc_len.append(sum(freq.values()))
            for t in freq:
                df[t] += 1
        self.df = dict(df)
        self.N = len(self.ids)
        self.avgdl = (sum(self.doc_len) / self.N) if self.N else 0.0
        self._idf = {}
        for t, n in self.df.items():
            # Lucene BM25 IDF，保证非负
            self._idf[t] = math.log(1.0 + (self.N - n + 0.5) / (n + 0.5))

    def idf(self, term: str) -> float:
        if term in self._idf:
            return self._idf[term]
        return math.log(1.0 + (self.N + 0.5) / 0.5) if self.N else 0.0

    def score_doc(self, i: int, query_tf: dict[str, int]) -> float:
        if not query_tf or self.N == 0:
            return 0.0
        dl = self.doc_len[i]
        denom_scale = self.k1 * (1.0 - self.b + self.b * (dl / self.avgdl if self.avgdl else 0))
        freq = self.tf[i]
        s = 0.0
        for t, qf in query_tf.items():
            tf = freq.get(t)
            if not tf:
                continue
            idf = self.idf(t)
            s += idf * (tf * (self.k1 + 1.0) / (tf + denom_scale)) * qf
        return s

    def search(
        self,
        query_tokens: list[str],
        *,
        project_id: str | None = None,
        asset_type: str | None = None,
        format_: str | None = None,
        triangle_min: int | None = None,
        triangle_max: int | None = None,
        cross_project: bool = False,
        top_k: int = 10,
    ) -> list[dict[str, Any]]:
        qtf: dict[str, int] = defaultdict(int)
        for t in query_tokens:
            if t:
                qtf[t] += 1
        if not qtf:
            return []
        scored: list[tuple[float, int]] = []
        for i, a in enumerate(self.docs):
            if not _pass_filters(
                a,
                project_id=project_id,
                asset_type=asset_type,
                format_=format_,
                triangle_min=triangle_min,
                triangle_max=triangle_max,
                cross_project=cross_project,
            ):
                continue
            s = self.score_doc(i, qtf)
            if s > 0:
                scored.append((s, i))
        scored.sort(key=lambda x: (-x[0], self.ids[x[1]]))
        out = []
        for s, i in scored[: max(top_k, 0)]:
            rec = dict(self.docs[i])
            rec["score"] = float(s)
            rec["asset_id"] = rec.get("id")
            rec["mode"] = "bm25"
            out.append(rec)
        return out


_lock = threading.Lock()
_cached: BM25Index | None = None
_cached_fp: tuple | None = None


def _fingerprint(assets: list[dict[str, Any]]) -> tuple:
    return (len(assets), tuple(sorted(a["id"] for a in assets)))


def get_index(force: bool = False) -> BM25Index:
    global _cached, _cached_fp
    # 可检索状态与语义层一致：已通过或申诉通过
    assets = [
        a
        for a in list_assets()
        if a.get("status") in ("approved", "appeal_passed")
    ]
    fp = _fingerprint(assets)
    with _lock:
        if _cached is not None and _cached_fp == fp and not force:
            return _cached
        idx = BM25Index()
        idx.build(assets)
        _cached = idx
        _cached_fp = fp
        return _cached


def document_tokens(asset: dict[str, Any]) -> list[str]:
    tokens: list[str] = []

    def add(text: str | None, weight: int) -> None:
        if not text:
            return
        toks = tokenize(str(text))
        for _ in range(max(int(weight), 1)):
            tokens.extend(toks)

    filename = asset.get("original_filename") or ""
    add(filename, FIELD_WEIGHTS["original_filename"])
    stem = Path(filename).stem if filename else ""
    add(stem, FIELD_WEIGHTS["stem"])

    # 路径与 id：kenney/mini-dungeon/weapon-sword
    path = asset.get("original_path") or ""
    aid = asset.get("id") or ""
    # 取 raw 之后的相对段，避免 /workspace/... 噪声
    path_bits = aid
    if "data/raw/" in path.replace("\\", "/"):
        path_bits = path.replace("\\", "/").split("data/raw/", 1)[-1]
    add(path_bits, FIELD_WEIGHTS["path_bits"])
    add(asset.get("source_pack"), FIELD_WEIGHTS["source_pack"])
    add(asset.get("asset_type"), FIELD_WEIGHTS["asset_type"])
    add(asset.get("source"), 1)
    tags = asset.get("tags") or []
    if isinstance(tags, str):
        add(tags, FIELD_WEIGHTS["tags"])
    else:
        for t in tags:
            add(str(t), FIELD_WEIGHTS["tags"])
    add(asset.get("description"), FIELD_WEIGHTS["description"])
    add(asset.get("canonical_name"), FIELD_WEIGHTS["canonical_name"])
    return tokens


def _pass_filters(
    a: dict[str, Any],
    *,
    project_id: str | None,
    asset_type: str | None,
    format_: str | None,
    triangle_min: int | None,
    triangle_max: int | None,
    cross_project: bool,
) -> bool:
    if not cross_project and project_id and a.get("project_id") != project_id:
        return False
    if asset_type and a.get("asset_type") != asset_type:
        return False
    if format_ and a.get("format") != format_:
        return False
    tris = a.get("triangles") or 0
    try:
        tris = int(tris)
    except (TypeError, ValueError):
        tris = 0
    if triangle_min is not None and tris < triangle_min:
        return False
    if triangle_max is not None and tris > triangle_max:
        return False
    return True
