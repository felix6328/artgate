"""LanceDB 向量库。检索流程：先按项目 / 类型 / 格式 / 面数过滤，再在子集里做向量检索。

只有 status=approved（或 appeal_passed）的资产进入可检索库。
项目默认隔离：A 项目未公开资产不能被 B 项目搜到。
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np

from artgate.paths import INDEX_DIR, ensure_dirs

TABLE = "assets"
_db = None
_dim_checked = False


def _connect():
    global _db
    if _db is None:
        import lancedb

        ensure_dirs()
        INDEX_DIR.mkdir(parents=True, exist_ok=True)
        _db = lancedb.connect(str(INDEX_DIR))
    return _db


def _schema(dim: int):
    import pyarrow as pa

    return pa.schema([
        pa.field("asset_id", pa.string()),
        pa.field("vector", pa.list_(pa.float32(), dim)),
        pa.field("project_id", pa.string()),
        pa.field("asset_type", pa.string()),
        pa.field("format", pa.string()),
        pa.field("triangles", pa.int32()),
        pa.field("canonical_name", pa.string()),
        pa.field("original_filename", pa.string()),
        pa.field("tags", pa.string()),
        pa.field("description", pa.string()),
        pa.field("preview_path", pa.string()),
        pa.field("source", pa.string()),
        pa.field("license", pa.string()),
        pa.field("status", pa.string()),
    ])


def has_table() -> bool:
    db = _connect()
    names = db.table_names()
    return TABLE in names


def open_table():
    db = _connect()
    if TABLE not in db.table_names():
        return None
    return db.open_table(TABLE)


def upsert_vectors(rows: list[dict[str, Any]], dim: int) -> int:
    """rows 每条必须有 asset_id 与 vector (np.ndarray)。"""
    if not rows:
        return 0
    import pandas as pd

    db = _connect()
    records = []
    for r in rows:
        vec = np.asarray(r["vector"], dtype=np.float32).reshape(-1)
        if vec.shape[0] != dim:
            raise ValueError(f"向量维度 {vec.shape[0]} != {dim}")
        records.append({
            "asset_id": r["asset_id"],
            "vector": vec.tolist(),
            "project_id": r.get("project_id") or "",
            "asset_type": r.get("asset_type") or "",
            "format": r.get("format") or "",
            "triangles": int(r.get("triangles") or 0),
            "canonical_name": r.get("canonical_name") or "",
            "original_filename": r.get("original_filename") or "",
            "tags": r.get("tags") if isinstance(r.get("tags"), str) else ",".join(r.get("tags") or []),
            "description": r.get("description") or "",
            "preview_path": r.get("preview_path") or "",
            "source": r.get("source") or "",
            "license": r.get("license") or "",
            "status": r.get("status") or "approved",
        })
    df = pd.DataFrame(records)
    if TABLE in db.table_names():
        tbl = db.open_table(TABLE)
        # 先删后加，避免重复
        ids = [r["asset_id"] for r in records]
        # lance where 字符串
        if ids:
            quoted = ", ".join("'" + i.replace("'", "''") + "'" for i in ids)
            try:
                tbl.delete(f"asset_id IN ({quoted})")
            except Exception:
                pass
        tbl.add(df)
    else:
        db.create_table(TABLE, df, schema=_schema(dim))
    return len(records)


def remove_vector(asset_id: str) -> None:
    tbl = open_table()
    if tbl is None:
        return
    safe = asset_id.replace("'", "''")
    tbl.delete(f"asset_id = '{safe}'")


def search_vectors(
    query_vec: np.ndarray,
    *,
    project_id: str | None,
    asset_type: str | None = None,
    format_: str | None = None,
    triangle_min: int | None = None,
    triangle_max: int | None = None,
    cross_project: bool = False,
    top_k: int = 10,
    status: str = "approved",
) -> list[dict[str, Any]]:
    tbl = open_table()
    if tbl is None:
        return []
    vec = np.asarray(query_vec, dtype=np.float32).reshape(-1)
    where = []
    # 默认项目隔离
    if project_id and not cross_project:
        where.append(f"project_id = '{_esc(project_id)}'")
    if asset_type:
        where.append(f"asset_type = '{_esc(asset_type)}'")
    if format_:
        where.append(f"format = '{_esc(format_)}'")
    if triangle_min is not None:
        where.append(f"triangles >= {int(triangle_min)}")
    if triangle_max is not None:
        where.append(f"triangles <= {int(triangle_max)}")
    # 申诉通过也视为可检索
    if status == "approved":
        where.append("(status = 'approved' OR status = 'appeal_passed')")
    elif status:
        where.append(f"status = '{_esc(status)}'")
    where_s = " AND ".join(where) if where else None
    # 多取一些再截断
    k = max(top_k, 1)
    q = tbl.search(vec).limit(k)
    if where_s:
        try:
            q = q.where(where_s, prefilter=True)
        except TypeError:
            q = q.where(where_s)
    try:
        df = q.to_pandas()
    except Exception:
        # 过滤过严或空库
        return []
    results = []
    for _, row in df.iterrows():
        rec = row.to_dict()
        # lance 距离：可能是 _distance（L2）或 _relevance_score
        dist = rec.get("_distance")
        score = rec.get("_relevance_score")
        if score is None and dist is not None:
            # 余弦若以 1-cos 存，这里用 1/(1+d) 作展示分
            score = float(1.0 / (1.0 + float(dist)))
        rec["score"] = float(score) if score is not None else None
        rec.pop("vector", None)
        results.append(rec)
    return results


def count_indexed(project_id: str | None = None) -> int:
    tbl = open_table()
    if tbl is None:
        return 0
    try:
        if project_id:
            df = tbl.search().where(f"project_id = '{_esc(project_id)}'", prefilter=True).limit(100000).to_pandas()
            # 上面不理想。改用 to_arrow 或 count_rows
        n = tbl.count_rows(f"project_id = '{_esc(project_id)}'") if project_id else tbl.count_rows()
        return int(n)
    except Exception:
        try:
            return int(tbl.count_rows())
        except Exception:
            return 0


def _esc(s: str) -> str:
    return s.replace("'", "''")
