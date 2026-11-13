"""预检编排：全部规则跑完 → 仅当需要时调 VLM → 汇总给人。

不是自主 Agent。写操作（入检索库、改级别）不在本模块。
总体判定：
- 任一 block 项 fail → overall=block（不能直接入库，可申诉）
- 否则若有 warn 项 fail 或 VLM 建议 → overall=warn（进人工队列）
- 工具失败项不把 overall 改成 block，但会把 overall 至少升为 warn（待人工）
- 全通过 → overall=pass（仍默认进确认队列，通过后才入可检索库）
"""
from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from artgate.config import check_severity, load_template
from artgate.precheck import rules
from artgate.precheck.vlm import VLMResult, get_backend


def run_precheck(
    path: Path,
    project_id: str,
    *,
    asset_type: str = "prop",
    canonical_name: str | None = None,
    original_filename: str | None = None,
    tags: list[str] | None = None,
    preview_path: Path | None = None,
    lod: int | None = None,
    companion_files: list[Path] | None = None,
    vlm_backend: str | None = None,
    skip_vlm: bool = False,
    asset_id: str | None = None,
    file_size: int | None = None,
) -> dict[str, Any]:
    t0 = time.perf_counter()
    path = Path(path)
    template = load_template(project_id)
    filename = canonical_name or original_filename or path.name
    ext = path.suffix.lower().lstrip(".")
    size = file_size if file_size is not None else (path.stat().st_size if path.exists() else 0)
    lod_n = rules.infer_lod(filename, lod)

    items: list[dict[str, Any]] = []
    items.append(rules.check_naming(filename, template, check_severity(template, "naming")))
    items.append(rules.check_format(ext, template, check_severity(template, "format")))
    items.append(rules.check_file_size(size, template, check_severity(template, "file_size")))
    items.extend(rules.check_image(path, template, asset_type))
    items.extend(rules.check_gltf(path, template, asset_type, lod_n))
    items.extend(rules.check_texture_channels(path, template, asset_type, companion_files))

    # 内部记录项不参与判定
    visible = [it for it in items if not it["check_id"].startswith("_")]
    raw_inspect = next((it for it in items if it["check_id"] == "_mesh_inspect_raw"), None)

    vlm_result: VLMResult | None = None
    vlm_items: list[dict[str, Any]] = []
    # 仅当规则层没有 block fail、且模板启用了视觉项时调用 VLM（成本策略）
    has_block_fail = any(it["severity"] == "block" and it["status"] == "fail" for it in visible)
    visual_enabled = any(
        check_severity(template, cid) in ("warn", "block")
        for cid in ("name_content_mismatch", "style_drift")
    )
    if skip_vlm:
        vlm_result = VLMResult(ran=False, backend="skipped", status="skipped", message="调用方要求跳过 VLM。")
    elif has_block_fail:
        vlm_result = VLMResult(
            ran=False,
            backend=get_backend(vlm_backend).name,
            status="skipped",
            message="规则层已有阻断项，按成本策略不调用 VLM。",
        )
    elif not visual_enabled:
        vlm_result = VLMResult(ran=False, backend="disabled", status="skipped", message="模板未启用视觉项。")
    else:
        backend = get_backend(vlm_backend)
        preview = Path(preview_path) if preview_path else _guess_preview(path)
        refs = [Path(p) for p in (template.get("style_reference") or {}).get("images") or [] if p]
        vlm_result = backend.review(
            preview,
            filename,
            tags or [],
            refs,
            {"style": template.get("style"), "project_id": project_id},
            asset_id=asset_id,
        )
        vlm_items = _vlm_to_items(vlm_result, template)

    overall = _overall(visible + vlm_items)
    duration_ms = (time.perf_counter() - t0) * 1000

    tools = {}
    if raw_inspect:
        tools["mesh_inspect"] = raw_inspect.get("evidence")
    return {
        "project_id": project_id,
        "template_name": template.get("name"),
        "filename": filename,
        "original_filename": original_filename or path.name,
        "asset_type": asset_type,
        "lod": lod_n,
        "overall": overall,  # pass | warn | block
        "items": visible + vlm_items,
        "vlm": vlm_result.to_dict() if vlm_result else None,
        "duration_ms": round(duration_ms, 2),
        "tools": tools,
        "policy": {
            "block_only_on_deterministic_fail": True,
            "vlm_default": "warn",
            "tool_failure_does_not_block": True,
            "no_auto_reject_on_warn": True,
            "no_auto_delete": True,
        },
    }


def _guess_preview(path: Path) -> Path | None:
    for ext in (".png", ".jpg", ".jpeg"):
        cand = path.with_suffix(ext)
        if cand.exists():
            return cand
    return path if path.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"} else None


def _vlm_to_items(result: VLMResult, template: dict) -> list[dict[str, Any]]:
    items = []
    if not result.ran:
        for cid, title in (
            ("name_content_mismatch", "文件名与内容是否一致（VLM）"),
            ("style_drift", "是否偏离风格参考板（VLM）"),
        ):
            items.append({
                "check_id": cid,
                "title": title,
                "severity": check_severity(template, cid),
                "status": "not_run",
                "measured": None,
                "threshold": f"置信度 ≥ {(template_vlm_threshold())}",
                "message": result.message or "视觉项未完成",
                "evidence": {"vlm_status": result.status, "backend": result.backend},
                "source": "vlm",
            })
        return items

    by_code = {iss.issue_code: iss for iss in result.issues}
    mapping = {
        "name_content_mismatch": "文件名与内容是否一致（VLM）",
        "style_drift": "是否偏离风格参考板（VLM）",
    }
    for cid, title in mapping.items():
        iss = by_code.get(cid)
        # also a combined "none"
        if iss is None:
            # if only "none" or "uncertain"
            none = by_code.get("none") or by_code.get("uncertain")
            if none and cid == "name_content_mismatch" and none.issue_code == "none":
                items.append({
                    "check_id": cid,
                    "title": title,
                    "severity": check_severity(template, cid),
                    "status": "pass",
                    "measured": {"confidence": none.confidence, "verdict": none.verdict},
                    "threshold": f"置信度 ≥ {template_vlm_threshold()}",
                    "message": none.evidence or "未发现名实不符",
                    "evidence": none.__dict__,
                    "source": f"vlm:{result.backend}",
                })
                continue
            if result.status in ("low_confidence",) and cid not in by_code:
                items.append({
                    "check_id": cid,
                    "title": title,
                    "severity": check_severity(template, cid),
                    "status": "uncertain",
                    "message": "低置信，不给通过建议",
                    "evidence": result.to_dict(),
                    "source": f"vlm:{result.backend}",
                })
                continue
            # 该项未提到，视为未检出问题
            items.append({
                "check_id": cid,
                "title": title,
                "severity": check_severity(template, cid),
                "status": "pass" if result.status == "ok" else "not_run",
                "message": "VLM 未提出该项问题" if result.status == "ok" else result.message,
                "source": f"vlm:{result.backend}",
            })
            continue
        fail = iss.verdict in ("mismatch", "drift")
        status = "fail" if fail else ("uncertain" if iss.verdict == "uncertain" else "pass")
        items.append({
            "check_id": cid,
            "title": title,
            "severity": iss.suggested_severity if iss.suggested_severity in ("warn", "block", "info") else check_severity(template, cid),
            "status": status,
            "measured": {"confidence": iss.confidence, "verdict": iss.verdict},
            "threshold": f"置信度 ≥ {template_vlm_threshold()}",
            "message": iss.evidence,
            "evidence": iss.__dict__,
            "source": f"vlm:{result.backend}",
        })
        # 强制：VLM 默认不得 block，除非模板已显式把该项升为 block（本项目默认 warn）
        if items[-1]["severity"] == "block" and check_severity(template, cid) != "block":
            items[-1]["severity"] = "warn"
            items[-1]["message"] += "（已按平台策略把 VLM 建议限制为 warn）"
    return items


def template_vlm_threshold() -> float:
    from artgate.config import settings

    return float((settings().get("vlm") or {}).get("confidence_threshold") or 0.6)


def _overall(items: list[dict[str, Any]]) -> str:
    block_fail = any(it["severity"] == "block" and it["status"] == "fail" for it in items)
    if block_fail:
        return "block"
    warn_fail = any(
        it["severity"] == "warn" and it["status"] in ("fail", "tool_failed", "uncertain")
        for it in items
    )
    tool_failed = any(it["status"] == "tool_failed" for it in items)
    if warn_fail or tool_failed:
        return "warn"
    return "pass"
