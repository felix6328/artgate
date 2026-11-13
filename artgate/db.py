from __future__ import annotations

import json
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Iterator

from artgate.paths import DB_PATH, ensure_dirs

SHANGHAI = timezone(timedelta(hours=8))
_local = threading.local()


def now_iso() -> str:
    return datetime.now(SHANGHAI).isoformat(timespec="seconds")


def connect(path: Path | None = None) -> sqlite3.Connection:
    ensure_dirs()
    p = path or DB_PATH
    conn = sqlite3.connect(p, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def get_conn() -> sqlite3.Connection:
    conn = getattr(_local, "conn", None)
    if conn is None:
        conn = connect()
        _local.conn = conn
        init_schema(conn)
    return conn


def init_schema(conn: sqlite3.Connection | None = None) -> None:
    c = conn or get_conn()
    c.executescript(
        """
        CREATE TABLE IF NOT EXISTS assets (
            id TEXT PRIMARY KEY,
            file_hash TEXT NOT NULL,
            original_path TEXT,
            original_filename TEXT,
            canonical_name TEXT,
            preview_path TEXT,
            project_id TEXT NOT NULL,
            asset_type TEXT,
            format TEXT,
            triangles INTEGER,
            tex_max_side INTEGER,
            file_size INTEGER,
            license TEXT,
            source TEXT,
            source_pack TEXT,
            tags TEXT,
            description TEXT,
            status TEXT NOT NULL DEFAULT 'pending',
            lod INTEGER DEFAULT 0,
            metadata TEXT,
            created_at TEXT,
            updated_at TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_assets_project ON assets(project_id);
        CREATE INDEX IF NOT EXISTS idx_assets_status ON assets(status);
        CREATE INDEX IF NOT EXISTS idx_assets_hash ON assets(file_hash);

        CREATE TABLE IF NOT EXISTS precheck_reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            asset_id TEXT NOT NULL,
            project_id TEXT,
            overall TEXT,
            report_json TEXT NOT NULL,
            duration_ms REAL,
            created_at TEXT,
            FOREIGN KEY (asset_id) REFERENCES assets(id)
        );

        CREATE TABLE IF NOT EXISTS reviews (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            asset_id TEXT NOT NULL,
            action TEXT NOT NULL,
            reason TEXT,
            reviewer TEXT,
            previous_status TEXT,
            new_status TEXT,
            created_at TEXT,
            FOREIGN KEY (asset_id) REFERENCES assets(id)
        );

        CREATE TABLE IF NOT EXISTS cost_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            kind TEXT NOT NULL,
            asset_id TEXT,
            input_hash TEXT,
            duration_ms REAL,
            estimated_cny REAL,
            ok INTEGER,
            details TEXT,
            created_at TEXT
        );
        """
    )
    c.commit()


@contextmanager
def tx() -> Iterator[sqlite3.Connection]:
    c = get_conn()
    try:
        yield c
        c.commit()
    except Exception:
        c.rollback()
        raise


def row_to_dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
    if row is None:
        return None
    d = dict(row)
    for key in ("tags", "metadata"):
        if d.get(key) and isinstance(d[key], str):
            try:
                d[key] = json.loads(d[key])
            except json.JSONDecodeError:
                pass
    return d


def upsert_asset(data: dict[str, Any]) -> None:
    data = dict(data)
    data.setdefault("created_at", now_iso())
    data["updated_at"] = now_iso()
    if isinstance(data.get("tags"), (list, dict)):
        data["tags"] = json.dumps(data["tags"], ensure_ascii=False)
    if isinstance(data.get("metadata"), (list, dict)):
        data["metadata"] = json.dumps(data["metadata"], ensure_ascii=False)
    cols = [
        "id", "file_hash", "original_path", "original_filename", "canonical_name",
        "preview_path", "project_id", "asset_type", "format", "triangles",
        "tex_max_side", "file_size", "license", "source", "source_pack", "tags",
        "description", "status", "lod", "metadata", "created_at", "updated_at",
    ]
    vals = [data.get(c) for c in cols]
    placeholders = ",".join("?" * len(cols))
    assignments = ",".join(f"{c}=excluded.{c}" for c in cols if c not in ("id", "created_at"))
    sql = f"INSERT INTO assets ({','.join(cols)}) VALUES ({placeholders}) ON CONFLICT(id) DO UPDATE SET {assignments}"
    conn = get_conn()
    conn.execute(sql, vals)
    conn.commit()


def get_asset(asset_id: str) -> dict[str, Any] | None:
    row = get_conn().execute("SELECT * FROM assets WHERE id=?", (asset_id,)).fetchone()
    return row_to_dict(row)


def list_assets(
    project_id: str | None = None,
    status: str | None = None,
    asset_type: str | None = None,
) -> list[dict[str, Any]]:
    q = "SELECT * FROM assets WHERE 1=1"
    args: list[Any] = []
    if project_id:
        q += " AND project_id=?"
        args.append(project_id)
    if status:
        q += " AND status=?"
        args.append(status)
    if asset_type:
        q += " AND asset_type=?"
        args.append(asset_type)
    q += " ORDER BY updated_at DESC"
    return [row_to_dict(r) for r in get_conn().execute(q, args)]  # type: ignore[misc]


def set_status(asset_id: str, status: str) -> None:
    get_conn().execute(
        "UPDATE assets SET status=?, updated_at=? WHERE id=?",
        (status, now_iso(), asset_id),
    )
    get_conn().commit()


def save_report(asset_id: str, project_id: str, overall: str, report: dict, duration_ms: float) -> int:
    cur = get_conn().execute(
        "INSERT INTO precheck_reports (asset_id, project_id, overall, report_json, duration_ms, created_at) VALUES (?,?,?,?,?,?)",
        (asset_id, project_id, overall, json.dumps(report, ensure_ascii=False), duration_ms, now_iso()),
    )
    get_conn().commit()
    return int(cur.lastrowid)


def latest_report(asset_id: str) -> dict[str, Any] | None:
    row = get_conn().execute(
        "SELECT * FROM precheck_reports WHERE asset_id=? ORDER BY id DESC LIMIT 1",
        (asset_id,),
    ).fetchone()
    if not row:
        return None
    d = dict(row)
    d["report"] = json.loads(d.pop("report_json"))
    return d


def add_review(asset_id: str, action: str, reason: str, reviewer: str, prev: str, new: str) -> None:
    get_conn().execute(
        "INSERT INTO reviews (asset_id, action, reason, reviewer, previous_status, new_status, created_at) VALUES (?,?,?,?,?,?,?)",
        (asset_id, action, reason, reviewer, prev, new, now_iso()),
    )
    get_conn().commit()


def list_reviews(asset_id: str | None = None) -> list[dict[str, Any]]:
    if asset_id:
        rows = get_conn().execute(
            "SELECT * FROM reviews WHERE asset_id=? ORDER BY id DESC", (asset_id,)
        ).fetchall()
    else:
        rows = get_conn().execute("SELECT * FROM reviews ORDER BY id DESC LIMIT 200").fetchall()
    return [dict(r) for r in rows]


def log_cost(
    kind: str,
    *,
    asset_id: str | None = None,
    input_hash: str | None = None,
    duration_ms: float = 0,
    estimated_cny: float = 0,
    ok: bool = True,
    details: dict | None = None,
) -> None:
    get_conn().execute(
        "INSERT INTO cost_events (kind, asset_id, input_hash, duration_ms, estimated_cny, ok, details, created_at) VALUES (?,?,?,?,?,?,?,?)",
        (
            kind,
            asset_id,
            input_hash,
            duration_ms,
            estimated_cny,
            1 if ok else 0,
            json.dumps(details or {}, ensure_ascii=False),
            now_iso(),
        ),
    )
    get_conn().commit()


def cost_summary() -> dict[str, Any]:
    rows = get_conn().execute(
        """
        SELECT kind,
               COUNT(*) AS n,
               SUM(duration_ms) AS total_ms,
               AVG(duration_ms) AS avg_ms,
               SUM(estimated_cny) AS total_cny,
               SUM(CASE WHEN ok=1 THEN 1 ELSE 0 END) AS n_ok
        FROM cost_events
        GROUP BY kind
        """
    ).fetchall()
    return {
        "by_kind": [dict(r) for r in rows],
        "note": "estimated_cny 对本地嵌入为 0；VLM 若未实际调用则为 0。不要把假设单价写成实测账单。",
    }
