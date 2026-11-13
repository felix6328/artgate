"""确定性规则层：命名、格式、体积、图片规格。数值不来自模型。"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from artgate.config import check_severity, infer_lod_from_name, naming_regex, poly_budget_for, pot_policy
from artgate.precheck.image_specs import IMAGE_EXTS, inspect_image, is_power_of_two
from artgate.precheck.gltf_tools import GLTF_EXTS, inspect_mesh, validate_gltf

CheckItem = dict[str, Any]


def _item(
    check_id: str,
    title: str,
    severity: str,
    status: str,
    *,
    measured: Any = None,
    threshold: Any = None,
    message: str = "",
    evidence: Any = None,
    source: str = "rule",
) -> CheckItem:
    # status: pass / fail / skip / tool_failed / uncertain / not_run
    return {
        "check_id": check_id,
        "title": title,
        "severity": severity,  # block | warn | info
        "status": status,
        "measured": measured,
        "threshold": threshold,
        "message": message,
        "evidence": evidence,
        "source": source,
    }


def check_naming(filename: str, template: dict, severity: str) -> CheckItem:
    pat = naming_regex(template)
    ok = bool(pat.match(filename))
    return _item(
        "naming",
        "命名规范",
        severity,
        "pass" if ok else "fail",
        measured=filename,
        threshold=template.get("naming", {}).get("pattern"),
        message="符合命名规范" if ok else f"文件名不符合规范（示例：{template.get('naming', {}).get('example')}）",
        evidence={"pattern": pat.pattern, "example": template.get("naming", {}).get("example")},
    )


def check_format(ext: str, template: dict, severity: str) -> CheckItem:
    ext = ext.lstrip(".").lower()
    if ext == "jpeg":
        ext = "jpg"
    allowed = [a.lower() for a in (template.get("allowed_formats") or [])]
    # ktx2 允许但评测未覆盖：格式检查仍按配置放行，并在证据里标注
    ok = ext in allowed
    uncovered = ext == "ktx2" and "ktx2" in (template.get("uncovered") or ["ktx2_format_samples"])
    msg = "格式允许" if ok else f"格式 .{ext} 不在允许列表 {allowed} 中"
    if ok and ext == "ktx2":
        msg += "（配置允许 ktx2；本评测集未覆盖真实样本）"
    return _item(
        "format",
        "允许格式",
        severity,
        "pass" if ok else "fail",
        measured=ext,
        threshold=allowed,
        message=msg,
        evidence={"uncovered_ktx2": uncovered},
    )


def check_file_size(size_bytes: int, template: dict, severity: str) -> CheckItem:
    max_mb = float(template.get("max_file_size_mb") or 0)
    max_bytes = int(max_mb * 1024 * 1024)
    ok = size_bytes <= max_bytes if max_mb > 0 else True
    return _item(
        "file_size",
        "文件体积",
        severity,
        "pass" if ok else "fail",
        measured=size_bytes,
        threshold=max_bytes,
        message=f"{size_bytes} 字节，上限 {max_mb} MB",
    )


def check_image(path: Path, template: dict, asset_type: str) -> list[CheckItem]:
    items: list[CheckItem] = []
    if path.suffix.lower() not in IMAGE_EXTS:
        return items
    if path.suffix.lower() in GLTF_EXTS:
        return items
    spec = inspect_image(path)
    sev_pot = check_severity(template, "image_power_of_two")
    sev_side = check_severity(template, "image_max_side")
    if spec.get("tool_failed"):
        items.append(_item(
            "image_specs",
            "图片规格",
            "warn",
            "tool_failed",
            message=spec.get("reason") or "图片工具失败，待人工",
            evidence=spec,
        ))
        return items
    policy = pot_policy(template, asset_type, is_3d_texture=False)
    max_side = (template.get("texture") or {}).get("max_side")
    w, h = spec.get("width"), spec.get("height")
    if policy == "required":
        ok = bool(spec.get("power_of_two"))
        items.append(_item(
            "image_power_of_two",
            "分辨率是否为 2 的幂次",
            sev_pot,
            "pass" if ok else "fail",
            measured={"width": w, "height": h},
            threshold="width 与 height 均为 2 的幂次",
            message="是 2 的幂次" if ok else f"{w}×{h} 不是 2 的幂次",
            evidence=spec,
        ))
    else:
        items.append(_item(
            "image_power_of_two",
            "分辨率是否为 2 的幂次",
            "info",
            "skip",
            measured={"width": w, "height": h, "power_of_two": spec.get("power_of_two")},
            threshold=f"本类型 {asset_type} 不强制（产品判断：2D 精灵 / UI 常为非 POT）",
            message="本类型不强制 2 的幂次，已跳过拦截",
            evidence={"policy": policy},
        ))
    if max_side:
        ok = (spec.get("max_side") or 0) <= int(max_side)
        items.append(_item(
            "image_max_side",
            "贴图最长边",
            sev_side,
            "pass" if ok else "fail",
            measured=spec.get("max_side"),
            threshold=max_side,
            message=f"最长边 {spec.get('max_side')}，上限 {max_side}",
        ))
    return items


def check_gltf(path: Path, template: dict, asset_type: str, lod: int) -> list[CheckItem]:
    items: list[CheckItem] = []
    if path.suffix.lower() not in GLTF_EXTS:
        return items

    sev_valid = check_severity(template, "gltf_valid")
    val = validate_gltf(path)
    if val.get("tool_failed"):
        items.append(_item(
            "gltf_valid",
            "glTF 规范校验（Khronos Validator）",
            "warn",  # 工具失败不得当作规范错误去 block
            "tool_failed",
            message="官方校验器失败，待人工。不会改由模型替代。",
            evidence=val,
            source="khronos-gltf-validator",
        ))
    else:
        passed = bool(val.get("passed"))
        n_err = val.get("num_errors", 0)
        n_warn = val.get("num_warnings", 0)
        items.append(_item(
            "gltf_valid",
            "glTF 规范校验（Khronos Validator）",
            sev_valid,
            "pass" if passed else "fail",
            measured={"num_errors": n_err, "num_warnings": n_warn},
            threshold="num_errors == 0（warning 不阻断）",
            message=(
                f"通过（errors={n_err}, warnings={n_warn}）"
                if passed
                else f"校验失败：{n_err} 个 error。warning 不作为阻断。"
            ),
            evidence={
                "errors": val.get("errors"),
                "warnings": val.get("warnings"),
                "validator_version": val.get("validator_version"),
            },
            source="khronos-gltf-validator",
        ))

    sev_poly = check_severity(template, "poly_budget")
    sev_tex = check_severity(template, "texture_max_side_3d")
    sev_pot = check_severity(template, "texture_power_of_two_3d")
    insp = inspect_mesh(path)
    if insp.get("tool_failed") and not insp.get("ok"):
        items.append(_item(
            "mesh_stats",
            "网格与贴图统计（glTF-Transform）",
            "warn",
            "tool_failed",
            message="官方 inspect 失败且回退也失败，待人工。不会改由模型口算面数。",
            evidence=insp,
            source="gltf-transform-inspect",
        ))
        return items

    source = insp.get("tool", "gltf-transform-inspect")
    fallback_note = "（使用 Python 回退，官方工具失败）" if insp.get("used_fallback") else ""
    triangles = insp.get("triangles")
    budget = poly_budget_for(template, asset_type, lod)
    if budget is None:
        items.append(_item(
            "poly_budget",
            "面数预算",
            "info",
            "skip",
            measured=triangles,
            message=f"该类型未配置面数预算{fallback_note}",
            source=source,
        ))
    else:
        # 工具失败拿不到面数时 status=tool_failed，不 block
        if triangles is None:
            items.append(_item(
                "poly_budget",
                "面数预算",
                "warn",
                "tool_failed",
                threshold=budget,
                message="未能取得面数，待人工",
                source=source,
            ))
        else:
            ok = int(triangles) <= int(budget)
            items.append(_item(
                "poly_budget",
                f"面数预算（LOD{lod}）",
                sev_poly,
                "pass" if ok else "fail",
                measured=triangles,
                threshold=budget,
                message=f"三角面 {triangles}，LOD{lod} 预算 {budget}{fallback_note}",
                evidence={"lod": lod, "used_fallback": insp.get("used_fallback")},
                source=source,
            ))

    max_side_limit = (template.get("texture") or {}).get("max_side")
    tex_max = insp.get("tex_max_side") or 0
    if max_side_limit and tex_max:
        ok = int(tex_max) <= int(max_side_limit)
        items.append(_item(
            "texture_max_side_3d",
            "3D 贴图最长边",
            sev_tex,
            "pass" if ok else "fail",
            measured=tex_max,
            threshold=max_side_limit,
            message=f"贴图最长边 {tex_max}，上限 {max_side_limit}{fallback_note}",
            evidence={"textures": insp.get("textures")},
            source=source,
        ))
    elif max_side_limit and not (insp.get("textures")):
        items.append(_item(
            "texture_max_side_3d",
            "3D 贴图最长边",
            "info",
            "skip",
            measured=0,
            threshold=max_side_limit,
            message="模型未检出贴图，跳过尺寸检查",
            source=source,
        ))

    pot = pot_policy(template, asset_type, is_3d_texture=True)
    if pot == "required" and insp.get("textures"):
        ok = bool(insp.get("textures_power_of_two"))
        items.append(_item(
            "texture_power_of_two_3d",
            "3D 贴图是否为 2 的幂次",
            sev_pot,
            "pass" if ok else "fail",
            measured=insp.get("textures"),
            threshold="每张贴图宽高均为 2 的幂次",
            message="全部为 2 的幂次" if ok else f"存在非 2 的幂次贴图{fallback_note}",
            source=source,
        ))
    elif pot != "required":
        items.append(_item(
            "texture_power_of_two_3d",
            "3D 贴图是否为 2 的幂次",
            "info",
            "skip",
            message="模板对该项不强制",
            source=source,
        ))

    # 通道：texture 类型在 check_texture_channels 里处理；模型按模板的 required_channels_severity_for_models
    required = (template.get("texture") or {}).get("required_channels") or []
    if required and asset_type != "texture":
        sev_ch = template.get("texture", {}).get("required_channels_severity_for_models", "warn")
        present = set(insp.get("channels") or [])
        missing = [c for c in required if c not in present]
        # 风格化 colormap 通常只有 albedo，写实模型可能只有部分通道
        items.append(_item(
            "required_channels_model",
            "模型 PBR 通道（信息 / 警告）",
            sev_ch,
            "pass" if not missing else "fail",
            measured=sorted(present),
            threshold=required,
            message="通道齐全" if not missing else f"缺少通道 {missing}（模型项按模板为 {sev_ch}，不是默认 block）",
            evidence={"present": sorted(present), "missing": missing},
            source=source,
        ))

    # 把 inspect 挂在最后一项的 evidence 之外，engine 会提升到 report.tools
    items.append(_item(
        "_mesh_inspect_raw",
        "工具原始统计",
        "info",
        "skip",
        evidence=insp,
        source=source,
        message="内部记录，不参与判定",
    ))
    return items


def check_texture_channels(path: Path, template: dict, asset_type: str, companion_files: list[Path] | None = None) -> list[CheckItem]:
    """贴图套装的必选通道。单张图无法自证是 albedo 还是 roughness，靠文件名约定。"""
    if asset_type != "texture":
        return []
    required = (template.get("texture") or {}).get("required_channels") or []
    if not required:
        return []
    sev = check_severity(template, "required_channels")
    names = [path.name.lower()]
    if companion_files:
        names.extend(p.name.lower() for p in companion_files)
    blob = " ".join(names)
    aliases = {
        "albedo": ["albedo", "diffuse", "diff", "basecolor", "base_color", "col", "color"],
        "normal": ["normal", "nor_gl", "nor_dx", "norm"],
        "roughness": ["roughness", "rough", "rgh"],
        "metallic": ["metallic", "metal", "met"],
    }
    present = []
    missing = []
    for ch in required:
        keys = aliases.get(ch, [ch])
        if any(k in blob for k in keys):
            present.append(ch)
        else:
            missing.append(ch)
    ok = not missing
    return [_item(
        "required_channels",
        "贴图套装必选通道",
        sev,
        "pass" if ok else "fail",
        measured=present,
        threshold=required,
        message="通道齐全（按文件名约定识别）" if ok else f"按文件名未识别到通道 {missing}",
        evidence={"filenames": names, "missing": missing},
    )]


def infer_lod(filename: str, metadata_lod: int | None = None) -> int:
    if metadata_lod is not None:
        return int(metadata_lod)
    return infer_lod_from_name(filename)
