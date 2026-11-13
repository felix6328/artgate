#!/usr/bin/env python3
"""离线评测：只报告脚本测到的数字，不编造。

检索：Recall@5 / Recall@10 / nDCG@10 / MRR，中英文分开。
对照：纯文件名搜索的同一套指标。
预检：规则层各检查项 Precision / Recall / F1，误拦率，漏放率。
体验：单次检索 P95、单资产规则预检耗时。
坏例写入 eval/badcases.md。
"""
from __future__ import annotations

import json
import math
import statistics
import sys
import time
from collections import defaultdict
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from artgate.config import load_template  # noqa: E402
from artgate.db import cost_summary  # noqa: E402
from artgate.paths import CATALOG, EVAL, REPO_ROOT  # noqa: E402
from artgate.precheck.engine import run_precheck  # noqa: E402
from artgate.search.query import metadata_search, search_image, search_text  # noqa: E402

GOLD_Q = EVAL / "gold_queries.yaml"
GOLD_P = EVAL / "gold_precheck.yaml"
RESULTS = EVAL / "results.md"
BAD = EVAL / "badcases.md"
RAW_JSON = EVAL / "results_raw.json"


def recall_at_k(relevant: set[str], retrieved: list[str], k: int) -> float | None:
    if not relevant:
        return None
    return len(relevant & set(retrieved[:k])) / len(relevant)


def rr(relevant: set[str], retrieved: list[str]) -> float | None:
    if not relevant:
        return None
    for i, a in enumerate(retrieved, 1):
        if a in relevant:
            return 1.0 / i
    return 0.0


def dcg(gains: list[float], k: int) -> float:
    s = 0.0
    for i, g in enumerate(gains[:k]):
        s += g / math.log2(i + 2)
    return s


def ndcg_at_k(grade: dict[str, int], retrieved: list[str], k: int) -> float | None:
    if not grade:
        return None
    gains = [float(grade.get(a, 0)) for a in retrieved[:k]]
    ideal = sorted(grade.values(), reverse=True)
    ideal_gains = [float(x) for x in ideal]
    denom = dcg(ideal_gains, k)
    if denom <= 0:
        return None
    return dcg(gains, k) / denom


def pct(xs, p):
    if not xs:
        return None
    ys = sorted(xs)
    if len(ys) == 1:
        return ys[0]
    k = (len(ys) - 1) * (p / 100.0)
    f = math.floor(k)
    c = math.ceil(k)
    if f == c:
        return ys[int(k)]
    return ys[f] * (c - k) + ys[c] * (k - f)


def mean(xs):
    return sum(xs) / len(xs) if xs else None


def fmt(x, nd=4):
    if x is None:
        return "（无）"
    if isinstance(x, float):
        return f"{x:.{nd}f}"
    return str(x)


def eval_search():
    gold = yaml.safe_load(GOLD_Q.read_text(encoding="utf-8"))
    queries = gold["queries"]
    rows = []
    latencies = []
    fn_rows = []
    # warmup
    try:
        search_text("剑", project_id="stylized_mobile", top_k=5)
    except Exception as e:
        print("warmup failed", e)

    for q in queries:
        rel = {r["asset_id"]: int(r["grade"]) for r in q.get("relevant") or []}
        rel_ids = {aid for aid, g in rel.items() if g >= 1}
        pid = q["project_id"]
        if q.get("modality") == "image":
            img = q.get("image_path")
            if not img or not Path(img).exists():
                rows.append({**q, "skip": "missing image"})
                continue
            res = search_image(Path(img), project_id=pid, top_k=10)
        else:
            res = search_text(q["query"], project_id=pid, top_k=10)
        retrieved = [r.get("id") or r.get("asset_id") for r in res.get("results") or []]
        retrieved = [x for x in retrieved if x]
        latencies.append(res.get("duration_ms") or 0)
        rec5 = recall_at_k(rel_ids, retrieved, 5)
        rec10 = recall_at_k(rel_ids, retrieved, 10)
        nd = ndcg_at_k(rel, retrieved, 10)
        mrr = rr(rel_ids, retrieved)
        row = {
            "id": q["id"],
            "query": q["query"],
            "lang": q["lang"],
            "modality": q.get("modality", "text"),
            "project_id": pid,
            "difficulty": q.get("difficulty"),
            "n_relevant": len(rel_ids),
            "retrieved": retrieved,
            "recall@5": rec5,
            "recall@10": rec10,
            "ndcg@10": nd,
            "mrr": mrr,
            "duration_ms": res.get("duration_ms"),
            "mode": res.get("mode"),
            "warnings": res.get("warnings") or [],
        }
        rows.append(row)

        if q.get("modality") != "image":
            fn = metadata_search(q["query"], project_id=pid, top_k=10)
            fn_ids = [r.get("id") or r.get("asset_id") for r in fn]
            fn_ids = [x for x in fn_ids if x]
            fn_rows.append({
                "id": q["id"],
                "lang": q["lang"],
                "recall@5": recall_at_k(rel_ids, fn_ids, 5),
                "recall@10": recall_at_k(rel_ids, fn_ids, 10),
                "ndcg@10": ndcg_at_k(rel, fn_ids, 10),
                "mrr": rr(rel_ids, fn_ids),
                "retrieved": fn_ids,
            })
        print(f"  {q['id']} {q['query']!r} R@10={fmt(rec10)} nDCG={fmt(nd)} nrel={len(rel_ids)}")

    def agg(subset):
        def col(name):
            xs = [r[name] for r in subset if r.get(name) is not None]
            return {"n": len(xs), "mean": mean(xs)}
        return {k: col(k) for k in ("recall@5", "recall@10", "ndcg@10", "mrr")}

    text_rows = [r for r in rows if r.get("modality") != "image" and "skip" not in r]
    img_rows = [r for r in rows if r.get("modality") == "image" and "skip" not in r]
    zh = [r for r in text_rows if r.get("lang") == "zh"]
    en = [r for r in text_rows if r.get("lang") == "en"]
    summary = {
        "all_text": agg(text_rows),
        "zh": agg(zh),
        "en": agg(en),
        "image": agg(img_rows),
        "filename_baseline_text": agg(fn_rows),
        "filename_baseline_zh": agg([r for r in fn_rows if r["lang"] == "zh"]),
        "filename_baseline_en": agg([r for r in fn_rows if r["lang"] == "en"]),
        "n_text": len(text_rows),
        "n_zh": len(zh),
        "n_en": len(en),
        "n_image": len(img_rows),
        "latency_ms": {
            "n": len(latencies),
            "mean": mean(latencies),
            "p50": pct(latencies, 50),
            "p95": pct(latencies, 95),
            "max": max(latencies) if latencies else None,
        },
    }
    return {"summary": summary, "rows": rows, "filename_rows": fn_rows, "gold_status": gold.get("status")}


def eval_precheck():
    gold = yaml.safe_load(GOLD_P.read_text(encoding="utf-8"))
    items = gold["items"]
    rows = []
    times = []
    # 按检查项累计
    # TP/FP/FN 只在金标对该检查项有期望时计数
    stats = defaultdict(lambda: {"tp": 0, "fp": 0, "fn": 0, "tn": 0})
    false_blocks = 0
    should_not_block = 0
    should_block = 0
    missed_blocks = 0  # 应拦却通过（overall != block）

    for it in items:
        path = ROOT / it["path"]
        if not path.exists():
            rows.append({**it, "skip": "file missing", "path": it["path"]})
            continue
        t0 = time.perf_counter()
        # 规则层评测：跳过 VLM。视觉项单独在 mock 模式下再跑一次可选。
        report = run_precheck(
            path,
            it["project_id"],
            asset_type=it.get("asset_type") or "prop",
            canonical_name=it.get("canonical_name") or path.name,
            original_filename=path.name,
            skip_vlm=True,
        )
        ms = (time.perf_counter() - t0) * 1000
        times.append(ms)
        pred = {c["check_id"]: c for c in report.get("items") or []}
        per = []
        for exp in it.get("expected") or []:
            if exp.get("layer") == "visual":
                per.append({**exp, "skipped_reason": "规则层评测排除视觉项"})
                continue
            cid = exp["check_id"]
            expected_status = exp["status"]
            got = pred.get(cid)
            got_status = got["status"] if got else "missing"
            # fail vs not-fail 作为二分类（对规则项）
            exp_fail = expected_status == "fail"
            pred_fail = got_status == "fail"
            if exp_fail and pred_fail:
                stats[cid]["tp"] += 1
                outcome = "tp"
            elif (not exp_fail) and pred_fail:
                stats[cid]["fp"] += 1
                outcome = "fp"
            elif exp_fail and (not pred_fail):
                stats[cid]["fn"] += 1
                outcome = "fn"
            else:
                stats[cid]["tn"] += 1
                outcome = "tn"
            per.append({
                "check_id": cid,
                "expected": expected_status,
                "predicted": got_status,
                "outcome": outcome,
                "measured": None if not got else got.get("measured"),
                "message": None if not got else got.get("message"),
            })
        overall = report.get("overall")
        exclude_fb = it.get("exclude_from_false_block")
        if it.get("should_block") is True:
            should_block += 1
            if overall != "block":
                missed_blocks += 1
        elif it.get("should_block") is False and not exclude_fb:
            should_not_block += 1
            if overall == "block":
                false_blocks += 1
        rows.append({
            "id": it["id"],
            "overall_expected": it.get("expected_overall"),
            "overall_pred": overall,
            "should_block": it.get("should_block"),
            "duration_ms": ms,
            "checks": per,
            "note": it.get("note"),
        })
        print(f"  {it['id']} overall={overall} expected_block={it.get('should_block')} {ms:.1f}ms")

    def prf(s):
        tp, fp, fn = s["tp"], s["fp"], s["fn"]
        prec = tp / (tp + fp) if (tp + fp) else None
        rec = tp / (tp + fn) if (tp + fn) else None
        if prec is None or rec is None or (prec + rec) == 0:
            f1 = None
        else:
            f1 = 2 * prec * rec / (prec + rec)
        return {**s, "precision": prec, "recall": rec, "f1": f1}

    by_check = {k: prf(v) for k, v in stats.items()}
    # 宏平均（只对同时有 tp+fn 或有定义的项）
    precs = [v["precision"] for v in by_check.values() if v["precision"] is not None]
    recs = [v["recall"] for v in by_check.values() if v["recall"] is not None]
    f1s = [v["f1"] for v in by_check.values() if v["f1"] is not None]
    false_block_rate = (false_blocks / should_not_block) if should_not_block else None
    miss_rate = (missed_blocks / should_block) if should_block else None
    return {
        "by_check": by_check,
        "macro_precision": mean(precs),
        "macro_recall": mean(recs),
        "macro_f1": mean(f1s),
        "false_block": {"n_false": false_blocks, "n_should_not": should_not_block, "rate": false_block_rate},
        "missed_block": {"n_missed": missed_blocks, "n_should": should_block, "rate": miss_rate},
        "latency_ms": {
            "n": len(times),
            "mean": mean(times),
            "p50": pct(times, 50),
            "p95": pct(times, 95),
            "max": max(times) if times else None,
        },
        "rows": rows,
        "n_items": len(items),
        "n_evaluated": len([r for r in rows if "skip" not in r]),
    }


def pick_badcases(search, precheck):
    """从实测结果归类坏例，不编。"""
    cases = []
    # 检索：Recall@10 == 0 或 很低
    for r in search["rows"]:
        if r.get("skip"):
            continue
        rec = r.get("recall@10")
        if rec is None:
            continue
        if rec <= 0:
            cases.append({
                "bucket": "检索完全未召回",
                "id": r["id"],
                "query": r["query"],
                "lang": r["lang"],
                "modality": r.get("modality"),
                "detail": f"Recall@10=0，返回 {r.get('retrieved')[:5]}",
                "next": "人工看预览是否域偏移、中文术语或金标本身有问题（金标待审）。",
            })
        elif rec < 0.5 and r.get("n_relevant", 0) <= 5:
            cases.append({
                "bucket": "检索召回偏低",
                "id": r["id"],
                "query": r["query"],
                "detail": f"Recall@10={rec:.3f}，n_rel={r.get('n_relevant')}，返回前5 {r.get('retrieved')[:5]}",
                "next": "对照文件名基线，判断是模型问题还是过滤/金标问题。",
            })
    for r in precheck["rows"]:
        for c in r.get("checks") or []:
            if c.get("outcome") == "fp":
                cases.append({
                    "bucket": "预检误报（FP）",
                    "id": r["id"],
                    "detail": f"{c['check_id']} 期望 {c['expected']} 实际 {c['predicted']}；{c.get('message')}",
                    "next": "核对阈值是否卡在预算边上，或校验器 warning 被误当 error。",
                })
            elif c.get("outcome") == "fn":
                cases.append({
                    "bucket": "预检漏报（FN）",
                    "id": r["id"],
                    "detail": f"{c['check_id']} 期望 {c['expected']} 实际 {c['predicted']}；{c.get('message')}",
                    "next": "核对工具是否失败、文件是否按预期注入。",
                })
        if r.get("should_block") is False and r.get("overall_pred") == "block":
            cases.append({
                "bucket": "误拦（合格样本被 block）",
                "id": r["id"],
                "detail": f"should_block=false，overall={r.get('overall_pred')}",
                "next": "这是使用率杀手，优先查哪一条 block 规则误触发。",
            })
        if r.get("should_block") is True and r.get("overall_pred") != "block":
            cases.append({
                "bucket": "漏放（应拦截却未 block）",
                "id": r["id"],
                "detail": f"should_block=true，overall={r.get('overall_pred')}",
                "next": "查规则是否未覆盖，或工具失败被降级。",
            })
    return cases


def write_reports(search, precheck, cases, extra):
    ss = search["summary"]
    lines = []
    def h(s):
        lines.append(s)
        lines.append("")

    h("# ArtGate 离线评测结果")
    lines.append(f"评测脚本：`eval/measure.py` 的入口为 `scripts/run_eval.py`。")
    lines.append(f"所有数字均由本次运行实测，没有手工填写。")
    lines.append("")
    lines.append("**金标状态：** 检索金标为 `auto_drafted_needs_review`，须经作者审阅后才能作为面试口径。")
    lines.append("审阅说明见 `eval/GOLD_QUERIES_README.md`。")
    lines.append("")
    h("## 1. 检索")
    lines.append(f"- 文本查询条数：全部 {ss['n_text']}（中文 {ss['n_zh']}，英文 {ss['n_en']}）；以图搜图 {ss['n_image']}。")
    lines.append("")
    lines.append("| 分组 | n | Recall@5 | Recall@10 | nDCG@10 | MRR |")
    lines.append("| --- | --- | --- | --- | --- | --- |")
    def row(name, key):
        a = ss[key]
        def m(metric):
            v = a[metric]["mean"]
            n = a[metric]["n"]
            return f"{fmt(v)} (n={n})" if v is not None else "（无）"
        n = ss.get("n_text") if key=="all_text" else ss.get("n_zh") if key=="zh" else ss.get("n_en") if key=="en" else ss.get("n_image") if key=="image" else a["recall@10"]["n"]
        lines.append(f"| {name} | {n} | {m('recall@5')} | {m('recall@10')} | {m('ndcg@10')} | {m('mrr')} |")
    row("语义 · 全部文本", "all_text")
    row("语义 · 中文", "zh")
    row("语义 · 英文", "en")
    row("语义 · 以图搜图", "image")
    row("文件名基线 · 全部文本", "filename_baseline_text")
    row("文件名基线 · 中文", "filename_baseline_zh")
    row("文件名基线 · 英文", "filename_baseline_en")
    lines.append("")
    lat = ss["latency_ms"]
    lines.append("### 检索时延（含本次进程内已加载模型后的查询）")
    lines.append("")
    lines.append(f"- 样本 n={lat['n']}：mean={fmt(lat['mean'],2)} ms，P50={fmt(lat['p50'],2)} ms，**P95={fmt(lat['p95'],2)} ms**，max={fmt(lat['max'],2)} ms。")
    lines.append(f"- 机器：见下方「环境」。第一次加载模型的时间不计入上述 P95（已先 warmup 一次）。")
    lines.append("")
    h("## 2. 预检（规则层）")
    lines.append("视觉层（VLM）本次默认未调用，不报告视觉精确率 / 召回率，简历该项保持占位。")
    lines.append("")
    lines.append(f"- 金标条数 {precheck['n_items']}，实际评测 {precheck['n_evaluated']}。")
    lines.append(f"- 宏平均 Precision={fmt(precheck['macro_precision'])}，Recall={fmt(precheck['macro_recall'])}，F1={fmt(precheck['macro_f1'])}（对各检查项简单平均，检查项样本量很小）。")
    fb = precheck["false_block"]
    mb = precheck["missed_block"]
    lines.append(f"- **误拦率**（should_block=false 却 overall=block）：{fb['n_false']} / {fb['n_should_not']} = {fmt(fb['rate'])}。")
    lines.append(f"- **漏放率**（should_block=true 却 overall≠block）：{mb['n_missed']} / {mb['n_should']} = {fmt(mb['rate'])}。")
    plat = precheck["latency_ms"]
    lines.append(f"- 单资产规则预检耗时 n={plat['n']}：mean={fmt(plat['mean'],2)} ms，P50={fmt(plat['p50'],2)} ms，**P95={fmt(plat['p95'],2)} ms**，max={fmt(plat['max'],2)} ms。")
    lines.append("")
    lines.append("| 检查项 | TP | FP | FN | TN | Precision | Recall | F1 |")
    lines.append("| --- | --- | --- | --- | --- | --- | --- | --- |")
    for k, v in sorted(precheck["by_check"].items()):
        lines.append(
            f"| `{k}` | {v['tp']} | {v['fp']} | {v['fn']} | {v['tn']} | {fmt(v['precision'])} | {fmt(v['recall'])} | {fmt(v['f1'])} |"
        )
    lines.append("")
    h("## 3. 环境与成本")
    lines.append(f"- 嵌入模型：OpenCLIP `xlm-roberta-base-ViT-B-32` / `laion5b_s13b_b90k`，device=cpu。")
    lines.append(f"- {extra.get('machine','')}")
    lines.append(f"- 本地嵌入 API 费用为 0。VLM 未配置时费用为 0。")
    cs = extra.get("cost") or {}
    lines.append(f"- 费用日志汇总：`{json.dumps(cs, ensure_ascii=False)}`")
    lines.append("")
    h("## 4. 限制（必须和数字一起讲）")
    lines.append("- 检索金标是自动起草、**未经作者审阅**的；相关集可能过宽或过窄。")
    lines.append("- 样本规模小（检索几十条查询、预检几十个注入样本），区间波动会很大，不能外推到生产库。")
    lines.append("- 资产来自公开 CC0 / 按模型许可的样本，风格以 Kenney 低模和 Poly Haven 写实为主，不能代表二次元或项目组私有风格。")
    lines.append("- 3D 检索用的是本仓库软件渲染的等轴测预览，不是引擎内截图或美术官方预览，域偏移会影响效果。")
    lines.append("- 以图搜图的若干条用库内预览搜自己，偏乐观。")
    lines.append("- 没有真实项目组用户的线上指标（点击率、申诉率）。")
    lines.append("- 未测真实 VLM，视觉层数字不得填写。")
    lines.append("")
    h("## 5. 逐条检索结果摘要")
    lines.append("| id | 查询 | 语言 | R@10 | nDCG@10 | n_rel | 前 3 个结果 |")
    lines.append("| --- | --- | --- | --- | --- | --- | --- |")
    for r in search["rows"]:
        if r.get("skip"):
            lines.append(f"| {r['id']} | {r.get('query')} | {r.get('lang')} | skip | | | {r.get('skip')} |")
            continue
        top = ", ".join((r.get("retrieved") or [])[:3])
        lines.append(f"| {r['id']} | {r['query']} | {r['lang']} | {fmt(r.get('recall@10'))} | {fmt(r.get('ndcg@10'))} | {r.get('n_relevant')} | `{top}` |")
    lines.append("")
    RESULTS.write_text("\n".join(lines), encoding="utf-8")

    bl = ["# ArtGate 坏例清单（来自本次评测，不是编的）", ""]
    if not cases:
        bl.append("本次自动规则没有抓到 Recall@10=0、预检 FP/FN 或误拦漏放。仍建议人工翻一遍逐条结果。")
    by = defaultdict(list)
    for c in cases:
        by[c["bucket"]].append(c)
    for bucket, items in by.items():
        bl.append(f"## {bucket}（{len(items)}）")
        bl.append("")
        for c in items:
            bl.append(f"- **{c.get('id','')}** {c.get('query','')}: {c.get('detail','')}")
            if c.get("next"):
                bl.append(f"  - 下一步：{c['next']}")
        bl.append("")
    BAD.write_text("\n".join(bl), encoding="utf-8")
    print("wrote", RESULTS)
    print("wrote", BAD)


def machine_info():
    import os, platform
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


def main():
    EVAL.mkdir(parents=True, exist_ok=True)
    print("== search ==")
    search = eval_search()
    print("== precheck ==")
    precheck = eval_precheck()
    cases = pick_badcases(search, precheck)
    extra = {"machine": machine_info(), "cost": cost_summary()}
    write_reports(search, precheck, cases, extra)
    RAW_JSON.write_text(json.dumps({
        "search_summary": search["summary"],
        "search_rows": search["rows"],
        "precheck": {k: v for k, v in precheck.items() if k != "rows"} | {"rows": precheck["rows"]},
        "badcases": cases,
        "machine": extra["machine"],
    }, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print("wrote", RAW_JSON)
    print("SEARCH TEXT Recall@10", search["summary"]["all_text"]["recall@10"])
    print("SEARCH ZH", search["summary"]["zh"]["recall@10"])
    print("SEARCH EN", search["summary"]["en"]["recall@10"])
    print("P95 search", search["summary"]["latency_ms"])
    print("PRECHECK FB", precheck["false_block"], "MISS", precheck["missed_block"])
    print("PRECHECK P95", precheck["latency_ms"])


if __name__ == "__main__":
    main()
