#!/usr/bin/env python3
"""ArtGate v2 离线评测：同一套金标，对比 v1 语义 / v2 混合 / BM25-only / 文件名基线。

不修改 eval/gold_queries.yaml。数字只来自本次脚本。
用固定种子按语言分层切 dev/test，供事后检验；本轮超参与词表在评测前冻结，
脚本不会根据任何分组结果改词表或权重。
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import random
import sys
import time
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from artgate.search.query import metadata_search, search_image, search_text  # noqa: E402

GOLD_Q = ROOT / "eval" / "gold_queries.yaml"
EXPECTED_GOLD_SHA256 = "8a019ae5a03e0ff3b0b69041d884861bda634905b12515839da020ed27d13f48"
SPLIT_SEED = 42
DEV_RATIO = 0.5
SPLIT_NAME = "artgate-v2-split-seed42-stratified-lang-50-50"

RESULTS_V2 = ROOT / "eval" / "results_v2.md"
RAW_V2 = ROOT / "eval" / "results_v2_raw.json"
SPLIT_PATH = ROOT / "eval" / "split_v2.json"
BAD = ROOT / "eval" / "badcases.md"

# 兵器相关查询的识别：按查询词本身，用于坏例分组，不参与调参。
WEAPON_HINTS = (
    "剑", "刀", "盾", "矛", "弓", "箭", "斧", "枪", "锤", "杖", "弩", "盔",
    "sword", "blade", "knife", "dagger", "shield", "spear", "pike", "lance",
    "bow", "arrow", "axe", "gun", "pistol", "rifle", "sniper", "shotgun",
    "hammer", "staff", "uzi", "grenade", "weapon",
)


def load_v1_metrics():
    spec = importlib.util.spec_from_file_location("v1eval", ROOT / "scripts" / "run_eval.py")
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader
    spec.loader.exec_module(mod)
    return mod


def gold_sha256() -> str:
    return hashlib.sha256(GOLD_Q.read_bytes()).hexdigest()


def assign_splits(text_queries: list[dict]) -> dict[str, str]:
    by_lang: dict[str, list[str]] = defaultdict(list)
    for q in text_queries:
        by_lang[str(q.get("lang") or "unk")].append(q["id"])
    assignment: dict[str, str] = {}
    counts: dict[str, dict[str, int]] = {}
    for lang, ids in sorted(by_lang.items()):
        ids = sorted(ids)
        rng = random.Random(SPLIT_SEED)
        rng.shuffle(ids)
        n_dev = int(round(len(ids) * DEV_RATIO))
        if len(ids) >= 2:
            n_dev = min(max(n_dev, 1), len(ids) - 1)
        for i, qid in enumerate(ids):
            assignment[qid] = "dev" if i < n_dev else "test"
        counts[lang] = {
            "n": len(ids),
            "dev": sum(1 for x in ids if assignment[x] == "dev"),
            "test": sum(1 for x in ids if assignment[x] == "test"),
        }
    return assignment, counts


def is_weapon_query(q: dict) -> bool:
    text = (q.get("query") or "").lower()
    return any(h.lower() in text for h in WEAPON_HINTS)


def agg(subset, keys=("recall@5", "recall@10", "ndcg@10", "mrr")):
    out = {}
    for k in keys:
        xs = [r[k] for r in subset if r.get(k) is not None]
        out[k] = {"n": len(xs), "mean": (sum(xs) / len(xs) if xs else None)}
    return out


def fmt(x, nd=4):
    if x is None:
        return "（无）"
    if isinstance(x, float):
        return f"{x:.{nd}f}"
    return str(x)


def fmt_cell(s, key="recall@10"):
    m = s.get(key) or {}
    return f"{fmt(m.get('mean'))} (n={m.get('n', 0)})"


def run_one(q, retriever: str, ev):
    rel = {r["asset_id"]: int(r["grade"]) for r in q.get("relevant") or []}
    rel_ids = {aid for aid, g in rel.items() if g >= 1}
    pid = q["project_id"]
    extra = {}
    if q.get("modality") == "image":
        img = q.get("image_path")
        path = Path(img) if img else None
        if path and not path.is_absolute():
            path = ROOT / path
        if not path or not path.exists():
            return {**{k: None for k in ("recall@5", "recall@10", "ndcg@10", "mrr")},
                    "id": q["id"], "skip": "missing image", "retrieved": [], "duration_ms": None}
        res = search_image(path, project_id=pid, top_k=10)
    else:
        res = search_text(q["query"], project_id=pid, top_k=10, retriever=retriever)
        extra = {
            "expansion": res.get("expansion"),
            "query_type": res.get("query_type"),
            "fusion": res.get("fusion"),
            "warnings": res.get("warnings") or [],
        }
    retrieved = [r.get("id") or r.get("asset_id") for r in res.get("results") or []]
    retrieved = [x for x in retrieved if x]
    ranks = []
    for r in res.get("results") or []:
        ranks.append({
            "id": r.get("id") or r.get("asset_id"),
            "score": r.get("score"),
            "component_ranks": r.get("component_ranks"),
            "filename": r.get("original_filename"),
        })
    return {
        "id": q["id"],
        "query": q["query"],
        "lang": q["lang"],
        "modality": q.get("modality", "text"),
        "project_id": pid,
        "difficulty": q.get("difficulty"),
        "n_relevant": len(rel_ids),
        "retrieved": retrieved,
        "ranks": ranks,
        "recall@5": ev.recall_at_k(rel_ids, retrieved, 5),
        "recall@10": ev.recall_at_k(rel_ids, retrieved, 10),
        "ndcg@10": ev.ndcg_at_k(rel, retrieved, 10),
        "mrr": ev.rr(rel_ids, retrieved),
        "duration_ms": res.get("duration_ms"),
        "mode": res.get("mode"),
        **extra,
    }


def filename_row(q, ev):
    rel = {r["asset_id"]: int(r["grade"]) for r in q.get("relevant") or []}
    rel_ids = {aid for aid, g in rel.items() if g >= 1}
    fn = metadata_search(q["query"], project_id=q["project_id"], top_k=10)
    fn_ids = [r.get("id") or r.get("asset_id") for r in fn]
    fn_ids = [x for x in fn_ids if x]
    return {
        "id": q["id"],
        "query": q["query"],
        "lang": q["lang"],
        "recall@5": ev.recall_at_k(rel_ids, fn_ids, 5),
        "recall@10": ev.recall_at_k(rel_ids, fn_ids, 10),
        "ndcg@10": ev.ndcg_at_k(rel, fn_ids, 10),
        "mrr": ev.rr(rel_ids, fn_ids),
        "retrieved": fn_ids,
    }


def machine_info():
    import os
    import platform
    cpu = platform.processor() or platform.machine()
    try:
        nproc = os.cpu_count()
    except Exception:
        nproc = None
    try:
        mem = Path("/proc/meminfo").read_text()
        mt = [ln for ln in mem.splitlines() if ln.startswith("MemTotal")][0]
    except Exception:
        mt = "unknown"
    return f"OS={platform.platform()} Python={platform.python_version()} CPU={cpu} nproc={nproc} {mt}"


def subset(rows, lang=None, split=None, assignment=None, ids=None):
    out = rows
    if lang:
        out = [r for r in out if r.get("lang") == lang]
    if split and assignment:
        out = [r for r in out if assignment.get(r["id"]) == split]
    if ids is not None:
        out = [r for r in out if r["id"] in ids]
    return out


def write_report(payload):
    s = payload
    assignment = s["assignment"]
    gold_status = s["gold_status"]
    sha = s["gold_sha256"]
    when = s["when"]
    machine = s["machine"]
    v1, v2, bm, fn = s["rows"]["v1"], s["rows"]["v2"], s["rows"]["bm25"], s["rows"]["filename"]
    img = s["rows"]["image"]
    lat = s["latency"]

    def block(rows, assignment=assignment):
        text = [r for r in rows if r.get("modality") != "image" and "skip" not in r]
        return {
            "all": agg(text),
            "zh": agg([r for r in text if r.get("lang") == "zh"]),
            "en": agg([r for r in text if r.get("lang") == "en"]),
            "dev": agg(subset(text, split="dev", assignment=assignment)),
            "test": agg(subset(text, split="test", assignment=assignment)),
            "dev_zh": agg(subset(text, lang="zh", split="dev", assignment=assignment)),
            "dev_en": agg(subset(text, lang="en", split="dev", assignment=assignment)),
            "test_zh": agg(subset(text, lang="zh", split="test", assignment=assignment)),
            "test_en": agg(subset(text, lang="en", split="test", assignment=assignment)),
            "n_text": len(text),
        }

    A = {"v1": block(v1), "v2": block(v2), "bm25": block(bm), "filename": block(fn)}

    def table_row(label, blk, group):
        g = blk[group]
        return (
            f"| {label} | {fmt_cell(g, 'recall@5')} | {fmt_cell(g, 'recall@10')} "
            f"| {fmt_cell(g, 'ndcg@10')} | {fmt_cell(g, 'mrr')} |"
        )

    lines = []
    L = lines.append
    L("# ArtGate v2 离线评测（与 v1 对比）")
    L("")
    L(f"评测时间：{when}（Asia/Shanghai）。")
    L("评测脚本：`scripts/run_eval_v2.py`。所有数字均由本次运行实测，没有手工填写。")
    L("")
    L(f"**金标文件未改动。** `eval/gold_queries.yaml` SHA256 = `{sha}`，与 v1 评测时一致。")
    L(f"金标状态仍为 `{gold_status}`，须经人工审阅后才能作为正式面试口径。")
    L("")
    L("## 方法（评测前冻结，未按本轮数字回改）")
    L("")
    L("- **v1**：仅 OpenCLIP 多语言语义检索（`retriever=semantic`），与 v1 标签提交行为一致。")
    L("- **v2**：语义一路（原查询，不扩展）+ BM25 一路（文件名 / 路径 / 标签 / 类型，查询经手写同义词扩展）→ **RRF 融合**（k=60）。")
    L("  选择 RRF 是因为 CLIP 展示分与 BM25 分数量纲不同，直接加权要引入归一化超参，更容易过拟合。")
    L("- **查询类型路由**：含中文或较长英文描述 → 两路等权（1.0/1.0）；标识符或 1–2 个英文实词（如 `a sword`）→ BM25 权重 1.5、语义 1.0。先验来自 v1 已发布的观察（英文短查询与英文文件名高度重叠），不是本轮网格搜索的结果。")
    L("- **消融**：BM25 + 同义词扩展、不融合语义；以及 v1 的纯文件名重叠基线（逻辑未改）。")
    L("- **以图搜图**：仍走纯语义，本轮方法不变。")
    L("- **同义词表**：`configs/synonyms_game_art.yaml`，手写领域词表。「剑」扩展为 sword/blade，**不**扩展为 knife。")
    L("  **泄漏风险**：词表写于 v1 评测之后，作者已经见过全量金标与坏例，不能声称完全看不见金标。dev/test 切分用于事后检验，**本轮没有根据 dev 结果增补词条或改权重**。")
    L("")
    L("## dev / test 切分")
    L("")
    L(f"- 名称：`{SPLIT_NAME}`。只切文本查询；以图搜图不参与切分。")
    L(f"- 按 `lang` 分层，组内对 query id 排序后用 `random.Random({SPLIT_SEED})` 打乱，各取约 {DEV_RATIO:.0%} 为 dev，其余为 test。")
    L(f"- 各语言条数：{json.dumps(s['split_counts'], ensure_ascii=False)}。")
    L("- 详细分配见 `eval/split_v2.json`。")
    L("")
    L("## 1. 主对比表（全量文本金标，与 v1 同一套题）")
    L("")
    L("| 系统 | 分组 | Recall@5 | Recall@10 | nDCG@10 | MRR |")
    L("| --- | --- | --- | --- | --- | --- |")
    for name, label in (("v1", "v1 语义"), ("v2", "v2 混合（RRF + 扩展）"),
                        ("bm25", "BM25 + 扩展（消融）"), ("filename", "文件名基线（v1 逻辑）")):
        blk = A[name]
        for g, gl in (("all", "全部文本"), ("zh", "中文"), ("en", "英文")):
            L(table_row(f"{label} · {gl}", blk, g).replace(f"| {label} · {gl} |", f"| {label} | {gl} |", 1) if False else
              f"| {label} | {gl} | {fmt_cell(blk[g], 'recall@5')} | {fmt_cell(blk[g], 'recall@10')} | {fmt_cell(blk[g], 'ndcg@10')} | {fmt_cell(blk[g], 'mrr')} |")
    L("")
    L("以图搜图（方法与 v1 相同，n 见下）：")
    img_agg = agg([r for r in img if "skip" not in r])
    L(f"- Recall@5={fmt_cell(img_agg, 'recall@5')}，Recall@10={fmt_cell(img_agg, 'recall@10')}，"
      f"nDCG@10={fmt_cell(img_agg, 'ndcg@10')}，MRR={fmt_cell(img_agg, 'mrr')}。查询图仍是库内预览，偏乐观。")
    L("")
    L("### 检索时延（模型已加载后的查询，已 warmup）")
    L("")
    L("| 系统 | n | mean (ms) | P50 | **P95** | max |")
    L("| --- | --- | --- | --- | --- | --- |")
    for key, label in (("v1", "v1 语义"), ("v2", "v2 混合"), ("bm25", "BM25 + 扩展")):
        lt = lat[key]
        L(f"| {label} | {lt['n']} | {fmt(lt['mean'], 2)} | {fmt(lt['p50'], 2)} | **{fmt(lt['p95'], 2)}** | {fmt(lt['max'], 2)} |")
    L("")
    L(f"机器：{machine}")
    L("第一次加载模型的时间不计入上述 P95。")
    L("")
    L("## 2. dev / test 分组（事后检验，本轮未在上面调参）")
    L("")
    L("| 系统 | 分组 | Recall@5 | Recall@10 | nDCG@10 | MRR |")
    L("| --- | --- | --- | --- | --- | --- |")
    for name, label in (("v1", "v1 语义"), ("v2", "v2 混合"), ("bm25", "BM25 + 扩展")):
        blk = A[name]
        for g, gl in (
            ("dev", "dev 全部"), ("test", "test 全部"),
            ("dev_zh", "dev 中文"), ("test_zh", "test 中文"),
            ("dev_en", "dev 英文"), ("test_en", "test 英文"),
        ):
            L(f"| {label} | {gl} | {fmt_cell(blk[g], 'recall@5')} | {fmt_cell(blk[g], 'recall@10')} | {fmt_cell(blk[g], 'ndcg@10')} | {fmt_cell(blk[g], 'mrr')} |")
    L("")
    L("若 test 相对 dev 没有明显塌陷，说明提升不只是记牢了某一半题目；即便如此，因作者见过 v1 全量坏例，仍不能排除词表覆盖与金标重叠带来的乐观。")
    L("")
    L("## 3. 相对 v1 的逐条变化（文本）")
    L("")

    v1_map = {r["id"]: r for r in v1 if "skip" not in r and r.get("modality") != "image"}
    v2_map = {r["id"]: r for r in v2 if "skip" not in r and r.get("modality") != "image"}
    bm_map = {r["id"]: r for r in bm if "skip" not in r}

    fixed, remaining, regress, improved, worsened = [], [], [], [], []
    for qid, a in sorted(v1_map.items()):
        b = v2_map.get(qid)
        if not b:
            continue
        r1, r2 = a.get("recall@10"), b.get("recall@10")
        if r1 is None or r2 is None:
            continue
        rec = {
            "id": qid,
            "query": a.get("query"),
            "lang": a.get("lang"),
            "split": assignment.get(qid),
            "v1": r1,
            "v2": r2,
            "delta": r2 - r1,
            "v1_ndcg": a.get("ndcg@10"),
            "v2_ndcg": b.get("ndcg@10"),
            "v1_top": (a.get("retrieved") or [])[:3],
            "v2_top": (b.get("retrieved") or [])[:3],
            "expansion": (b.get("expansion") or {}).get("added_terms"),
            "query_type": b.get("query_type"),
            "weapon": is_weapon_query(a),
        }
        if r1 <= 0 and r2 > 0:
            fixed.append(rec)
        elif r1 <= 0 and r2 <= 0:
            remaining.append(rec)
        elif r1 > 0 and r2 <= 0:
            regress.append(rec)
        elif r2 - r1 >= 0.15:
            improved.append(rec)
        elif r1 - r2 >= 0.15:
            worsened.append(rec)

    def dump_cases(title, cases, empty="（无）"):
        L(f"### {title}（{len(cases)} 条）")
        L("")
        if not cases:
            L(empty)
            L("")
            return
        L("| id | 查询 | 语言 | 分组 | v1 R@10 | v2 R@10 | Δ | 扩展词 | v2 前 3 |")
        L("| --- | --- | --- | --- | --- | --- | --- | --- | --- |")
        for c in cases:
            q = (c["query"] or "").replace("|", "\\|")
            top = ", ".join(c["v2_top"][:3])
            exp = ", ".join(c["expansion"] or []) or "—"
            L(f"| {c['id']} | {q} | {c['lang']} | {c['split']} | {fmt(c['v1'])} | {fmt(c['v2'])} | {c['delta']:+.4f} | {exp} | `{top}` |")
        L("")

    dump_cases("已修复：v1 Recall@10 = 0，v2 > 0", fixed)
    dump_cases("明显提升：v2 − v1 Recall@10 ≥ 0.15（且 v1 不是 0）", improved)
    dump_cases("仍未召回：v1 与 v2 的 Recall@10 都是 0", remaining)
    dump_cases("回退：v1 Recall@10 > 0，v2 = 0", regress)
    dump_cases("明显下降：v1 − v2 Recall@10 ≥ 0.15（v2 未到 0）", worsened)

    # 兵器专题
    weapon_ids = [r["id"] for r in v1_map.values() if is_weapon_query(r)]
    L("### 兵器类查询专题")
    L("")
    L("识别规则：查询文本含剑/盾/矛/弓/箭/枪/sword/shield/spear 等武器词，用于分组展示，**没有**据此改模型或词表。")
    L("")
    L("| id | 查询 | 分组 | v1 R@10 | v2 R@10 | BM25 R@10 | 文件名基线 | 扩展词 |")
    L("| --- | --- | --- | --- | --- | --- | --- | --- |")
    fn_map = {r["id"]: r for r in fn}
    for qid in weapon_ids:
        a, b, c = v1_map[qid], v2_map[qid], bm_map.get(qid, {})
        f = fn_map.get(qid, {})
        q = (a.get("query") or "").replace("|", "\\|")
        exp = ", ".join((b.get("expansion") or {}).get("added_terms") or []) or "—"
        L(f"| {qid} | {q} | {assignment.get(qid)} | {fmt(a.get('recall@10'))} | {fmt(b.get('recall@10'))} | {fmt(c.get('recall@10'))} | {fmt(f.get('recall@10'))} | {exp} |")
    L("")

    L("## 4. 限制（必须和数字一起讲）")
    L("")
    L("- 金标仍为自动起草、未经人工审阅。")
    L("- 同义词表的作者见过 v1 全量坏例，存在泄漏风险；dev/test 是缓解而不是消除。")
    L("- 样本仍然很小，区间波动会很大。")
    L("- 3D 预览仍是软件等轴测，语义一路的近形混淆（剑 vs 刀）并没有从模型上被「治好」，只是被词法一路托上来。换预览或做重排是后续，不是本轮声称已解决的事。")
    L("- 形状/颜色扩展（圆形→round、金色→gold）可能把 UI 圆钮、金色枪皮也拉进来，属于过度扩展风险。")
    L("- 以图搜图、规则预检本轮方法未改；预检数字仍以 `eval/results.md` 为准，未重跑。")
    L("")
    L("## 5. 环境")
    L("")
    L(f"- {machine}")
    L("- 嵌入模型仍为 OpenCLIP `xlm-roberta-base-ViT-B-32` / `laion5b_s13b_b90k`，CPU。")
    L("")

    RESULTS_V2.write_text("\n".join(lines) + "\n", encoding="utf-8")
    payload_out = {
        **s,
        "aggregates": A,
        "image_agg": img_agg,
        "changes": {
            "fixed": fixed,
            "improved": improved,
            "remaining": remaining,
            "regress": regress,
            "worsened": worsened,
            "weapon_ids": weapon_ids,
        },
    }
    # assignment etc may have non-json? fine
    return payload_out, {"fixed": fixed, "improved": improved, "remaining": remaining,
                         "regress": regress, "worsened": worsened, "weapon_ids": weapon_ids}


def write_badcases(changes, v1_map, v2_map, assignment):
    """在保留 v1 预检说明的同时，重写检索坏例为 v1 vs v2。"""
    lines = []
    L = lines.append
    L("# ArtGate 坏例清单（v1 vs v2）")
    L("")
    L("检索部分按同一套金标对比 v1 语义与 v2 混合检索。数字来自 `scripts/run_eval_v2.py`。")
    L("预检规则层本轮未重跑，口径与 v1 相同，详见 `eval/results.md` 第 2 节（18 条夹具上宏平均 1.00，样本量小）。")
    L("金标未经人工审阅。同义词表作者见过 v1 全量坏例，有泄漏风险。")
    L("")

    def section(title, cases, why):
        L(f"## {title}（{len(cases)}）")
        L("")
        L(why)
        L("")
        if not cases:
            L("（无）")
            L("")
            return
        for c in cases:
            L(f"### {c['id']}　{c['query']}")
            L("")
            L(f"- 语言 / 分组：{c['lang']} / {c['split']}")
            L(f"- v1 Recall@10 = {fmt(c['v1'])}，v2 Recall@10 = {fmt(c['v2'])}（Δ {c['delta']:+.4f}）")
            L(f"- v1 前 3：`{c['v1_top']}`")
            L(f"- v2 前 3：`{c['v2_top']}`")
            if c.get("expansion"):
                L(f"- 同义词扩展：{c['expansion']}")
            v2row = v2_map.get(c["id"], {})
            ranks = (v2row.get("ranks") or [])[:3]
            if ranks:
                L(f"- v2 前 3 的分路名次：{[{'id': r['id'], 'ranks': r.get('component_ranks'), 'file': r.get('filename')} for r in ranks]}")
            L("")

    section(
        "已修复（v1 完全未召回，v2 召回了）",
        changes["fixed"],
        "典型机制：中文查询经译名扩展后被 BM25 命中英文文件名，RRF 把词法第一名托到融合列表前面。语义一路本身往往仍把近形物体排在前面。",
    )
    section(
        "明显提升（Δ Recall@10 ≥ 0.15）",
        changes["improved"],
        "v1 已有部分召回，混合检索进一步提高。",
    )
    section(
        "仍未解决（两边 Recall@10 均为 0）",
        changes["remaining"],
        "词表没覆盖、文件名与查询对不上、或相关资产在语义与词法两路都进不了前 10。不要为这些条目事后补词。",
    )
    section(
        "回退（v1 有召回，v2 变为 0）",
        changes["regress"],
        "融合或扩展把不相关的词法命中抬上来，挤掉了原来语义能排进前 10 的相关资产。这是混合检索的真实代价，必须讲。",
    )
    section(
        "明显下降（Δ ≤ −0.15，但 v2 未到 0）",
        changes["worsened"],
        "同上，属于排序被词法干扰。",
    )
    L("## 兵器类查询还剩什么")
    L("")
    L("见 `eval/results_v2.md` 第 3 节的兵器专题表。语义一路的剑/刀混淆没有从模型上消失：")
    L("「一把剑」在 v2 能排到第一，是因为 BM25 在 `weapon-sword.glb` 上是第 1、语义上大约是第 30 多名，RRF 把它托上来。")
    L("若关掉词法一路，问题会回到 v1。后续若做重排或换预览，应在同一套金标上再比一次。")
    L("")
    BAD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main():
    ev = load_v1_metrics()
    sha = gold_sha256()
    if sha != EXPECTED_GOLD_SHA256:
        print("ERROR: gold_queries.yaml SHA256 mismatch.", sha, "expected", EXPECTED_GOLD_SHA256)
        print("Refuse to run: v2 eval requires the unchanged v1 gold set.")
        sys.exit(2)
    gold = yaml.safe_load(GOLD_Q.read_text(encoding="utf-8"))
    queries = gold["queries"]
    # 再次确认没有在内存里改写后写回——本脚本只读。
    text_q = [q for q in queries if q.get("modality") != "image"]
    img_q = [q for q in queries if q.get("modality") == "image"]
    assignment, split_counts = assign_splits(text_q)
    SPLIT_PATH.write_text(json.dumps({
        "name": SPLIT_NAME,
        "seed": SPLIT_SEED,
        "dev_ratio": DEV_RATIO,
        "counts": split_counts,
        "assignment": assignment,
        "note": "只用于事后分组报告。本轮词表与超参冻结，未按 dev 调参。",
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print("split", split_counts)

    print("warmup…")
    try:
        search_text("剑", project_id="stylized_mobile", top_k=5, retriever="semantic")
        search_text("剑", project_id="stylized_mobile", top_k=5, retriever="hybrid")
        search_text("剑", project_id="stylized_mobile", top_k=5, retriever="bm25")
    except Exception as e:
        print("warmup failed", e)

    rows = {"v1": [], "v2": [], "bm25": [], "filename": [], "image": []}
    for q in text_q:
        print(f"== {q['id']} {q['query']!r}")
        r1 = run_one(q, "semantic", ev)
        r2 = run_one(q, "hybrid", ev)
        rb = run_one(q, "bm25", ev)
        rf = filename_row(q, ev)
        rows["v1"].append(r1)
        rows["v2"].append(r2)
        rows["bm25"].append(rb)
        rows["filename"].append(rf)
        print(f"   v1={fmt(r1['recall@10'])} v2={fmt(r2['recall@10'])} bm25={fmt(rb['recall@10'])} fn={fmt(rf['recall@10'])}")

    for q in img_q:
        print(f"== image {q['id']}")
        rows["image"].append(run_one(q, "semantic", ev))

    def lat_of(rs):
        xs = [r["duration_ms"] for r in rs if r.get("duration_ms") is not None]
        return {
            "n": len(xs),
            "mean": ev.mean(xs),
            "p50": ev.pct(xs, 50),
            "p95": ev.pct(xs, 95),
            "max": max(xs) if xs else None,
        }

    # 文本查询的时延（不含 warmup）
    # 以图搜图时延不并入 v2 文本 P95
    when = datetime.now(ZoneInfo("Asia/Shanghai")).strftime("%Y-%m-%d %H:%M %Z")
    payload = {
        "when": when,
        "gold_sha256": sha,
        "gold_status": gold.get("status"),
        "assignment": assignment,
        "split_counts": split_counts,
        "split_name": SPLIT_NAME,
        "machine": machine_info(),
        "rows": rows,
        "latency": {
            "v1": lat_of(rows["v1"]),
            "v2": lat_of(rows["v2"]),
            "bm25": lat_of(rows["bm25"]),
        },
        "hyperparams_frozen": {
            "fusion": "rrf",
            "rrf_k": 60,
            "candidate_k": 50,
            "expand_for_bm25": True,
            "expand_for_semantic": False,
            "router_weights": {
                "filename_like": {"semantic": 1.0, "bm25": 1.5},
                "descriptive": {"semantic": 1.0, "bm25": 1.0},
            },
            "synonyms": "configs/synonyms_game_art.yaml",
            "tuned_on_dev": False,
        },
    }
    full, changes = write_report(payload)
    v1_map = {r["id"]: r for r in rows["v1"]}
    v2_map = {r["id"]: r for r in rows["v2"]}
    write_badcases(changes, v1_map, v2_map, assignment)

    # raw json：去掉过大的嵌套重复前精简
    RAW_V2.write_text(json.dumps({
        "when": when,
        "gold_sha256": sha,
        "gold_status": gold.get("status"),
        "split_counts": split_counts,
        "assignment": assignment,
        "hyperparams_frozen": payload["hyperparams_frozen"],
        "machine": payload["machine"],
        "latency": payload["latency"],
        "aggregates": full["aggregates"],
        "image_agg": full["image_agg"],
        "changes": {
            k: ([{"id": x["id"], "query": x.get("query"), "lang": x.get("lang"),
                  "split": x.get("split"), "v1": x.get("v1"), "v2": x.get("v2"),
                  "delta": x.get("delta")} for x in v] if k != "weapon_ids" else v)
            for k, v in changes.items()
        },
        "rows": {
            "v1": rows["v1"],
            "v2": rows["v2"],
            "bm25": rows["bm25"],
            "filename": rows["filename"],
            "image": rows["image"],
        },
    }, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print("wrote", RESULTS_V2)
    print("wrote", BAD)
    print("wrote", RAW_V2)
    print("GOLD SHA256 ok", sha)
    # 再读文件确认金标字节未变
    sha2 = gold_sha256()
    assert sha2 == EXPECTED_GOLD_SHA256, sha2


if __name__ == "__main__":
    main()
