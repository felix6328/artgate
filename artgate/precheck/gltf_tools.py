"""官方工具封装：Khronos glTF-Validator + glTF-Transform inspect。

失败时降级为 Python 结构检查 / trimesh 面数，并在报告里标明
「工具失败，待人工 / 使用了 Python 回退」，禁止改由 LLM 替代。
"""
from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

from artgate.paths import REPO_ROOT, NODE_MODULES
from artgate.precheck.image_specs import is_power_of_two

VALIDATE_JS = Path(__file__).resolve().parent / "gltf_validate.js"
INSPECT_JS = Path(__file__).resolve().parent / "gltf_inspect.js"
GLTF_EXTS = {".glb", ".gltf"}

# validator severity: 0=error, 1=warning, 2=info, 3=hint
SEV_NAME = {0: "error", 1: "warning", 2: "info", 3: "hint"}


def _node_bin() -> str:
    return shutil.which("node") or "node"


def node_available() -> bool:
    return shutil.which("node") is not None and (NODE_MODULES / "gltf-validator").exists()


def _run_node(script: Path, file: Path, timeout: int = 60) -> dict[str, Any]:
    if not script.exists():
        return {"ok": False, "tool_failed": True, "error": f"缺少脚本 {script}"}
    if shutil.which("node") is None:
        return {"ok": False, "tool_failed": True, "error": "未找到 node，无法调用官方工具"}
    try:
        proc = subprocess.run(
            [_node_bin(), str(script), str(file)],
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return {"ok": False, "tool_failed": True, "error": f"官方工具超时（{timeout}s）"}
    except OSError as e:
        return {"ok": False, "tool_failed": True, "error": f"无法启动 node: {e}"}
    raw = (proc.stdout or "").strip()
    if not raw:
        err = (proc.stderr or "").strip()[:500]
        return {"ok": False, "tool_failed": True, "error": f"官方工具无输出: {err}"}
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return {
            "ok": False,
            "tool_failed": True,
            "error": f"官方工具输出不是 JSON: {raw[:400]}",
        }
    return data


def _python_inspect_fallback(path: Path) -> dict[str, Any]:
    """trimesh / pygltflib 回退，仅在官方工具失败时使用，报告必须标明。"""
    try:
        import trimesh

        sc = trimesh.load(str(path), force="scene", process=False)
        geoms = list(sc.geometry.values()) if isinstance(sc, trimesh.Scene) else [sc]
        triangles = 0
        vertices = 0
        textures: list[dict[str, Any]] = []
        for g in geoms:
            if hasattr(g, "faces"):
                triangles += int(len(g.faces))
            if hasattr(g, "vertices"):
                vertices += int(len(g.vertices))
            vis = getattr(g, "visual", None)
            mat = getattr(vis, "material", None) if vis is not None else None
            img = None
            if mat is not None:
                img = getattr(mat, "baseColorTexture", None) or getattr(mat, "image", None)
            if img is not None and hasattr(img, "size"):
                w, h = img.size
                textures.append({"resolution": f"{w}x{h}", "width": w, "height": h, "slot": "baseColorTexture"})
        return {
            "ok": True,
            "tool": "python-trimesh-fallback",
            "tool_failed": False,
            "used_fallback": True,
            "triangles": triangles,
            "vertices": vertices,
            "textures": textures,
            "tex_max_side": max((t["width"] for t in textures), default=0),
            "channels": ["albedo"] if textures else [],
        }
    except Exception as e:
        return {
            "ok": False,
            "tool": "python-trimesh-fallback",
            "tool_failed": True,
            "used_fallback": True,
            "error": f"{type(e).__name__}: {e}",
        }


def _parse_resolution(s: str | None) -> tuple[int | None, int | None]:
    if not s or "x" not in str(s).lower():
        return None, None
    a, b = str(s).lower().split("x", 1)
    try:
        return int(a), int(b)
    except ValueError:
        return None, None


SLOT_TO_CHANNEL = {
    "baseColorTexture": "albedo",
    "basecolortexture": "albedo",
    "diffuseTexture": "albedo",
    "normalTexture": "normal",
    "metallicRoughnessTexture": "roughness",  # 合并贴图，同时视作 metallic+roughness 存在
    "occlusionTexture": "occlusion",
    "emissiveTexture": "emissive",
}


def inspect_mesh(path: Path) -> dict[str, Any]:
    official = _run_node(INSPECT_JS, path)
    if official.get("ok") and official.get("report"):
        report = official["report"]
        meshes = (report.get("meshes") or {}).get("properties") or []
        textures = (report.get("textures") or {}).get("properties") or []
        materials = (report.get("materials") or {}).get("properties") or []
        triangles = int(sum(int(m.get("glPrimitives") or 0) for m in meshes))
        vertices = int(sum(int(m.get("vertices") or 0) for m in meshes))
        tex_parsed = []
        max_side = 0
        channels: set[str] = set()
        all_pot = True
        for t in textures:
            w, h = _parse_resolution(t.get("resolution"))
            if w and h:
                max_side = max(max_side, w, h)
                if not (is_power_of_two(w) and is_power_of_two(h)):
                    all_pot = False
            else:
                all_pot = False if textures else all_pot
            for slot in t.get("slots") or []:
                ch = SLOT_TO_CHANNEL.get(str(slot), SLOT_TO_CHANNEL.get(str(slot).replace("Texture", "Texture"), None))
                if ch:
                    channels.add(ch)
                # metallicRoughness 同时算 metallic 与 roughness
                if str(slot) in ("metallicRoughnessTexture",):
                    channels.add("metallic")
                    channels.add("roughness")
            tex_parsed.append({
                "name": t.get("name"),
                "uri": t.get("uri"),
                "resolution": t.get("resolution"),
                "width": w,
                "height": h,
                "slots": t.get("slots"),
                "mimeType": t.get("mimeType"),
                "power_of_two": (is_power_of_two(w) and is_power_of_two(h)) if w and h else None,
            })
        # 也从材质 slots 补通道
        for mat in materials:
            for slot in mat.get("textures") or []:
                if slot == "metallicRoughnessTexture":
                    channels.add("metallic")
                    channels.add("roughness")
                elif slot in SLOT_TO_CHANNEL:
                    channels.add(SLOT_TO_CHANNEL[slot])
        return {
            "ok": True,
            "tool": "gltf-transform-inspect",
            "tool_failed": False,
            "used_fallback": False,
            "triangles": triangles,
            "vertices": vertices,
            "meshes": [{"name": m.get("name"), "glPrimitives": m.get("glPrimitives"), "vertices": m.get("vertices")} for m in meshes],
            "textures": tex_parsed,
            "tex_max_side": max_side,
            "textures_power_of_two": all_pot if textures else True,
            "channels": sorted(channels),
            "raw": report,
        }
    # 官方失败 → Python 回退
    fb = _python_inspect_fallback(path)
    fb["official_error"] = official.get("error") or official
    if fb.get("ok"):
        for t in fb.get("textures") or []:
            t["power_of_two"] = (
                is_power_of_two(t["width"]) and is_power_of_two(t["height"])
                if t.get("width") and t.get("height")
                else None
            )
        fb["textures_power_of_two"] = all(
            t.get("power_of_two") for t in (fb.get("textures") or [])
        ) if fb.get("textures") else True
    return fb


def validate_gltf(path: Path) -> dict[str, Any]:
    official = _run_node(VALIDATE_JS, path)
    if official.get("ok") and official.get("result"):
        result = official["result"]
        issues = result.get("issues") or {}
        messages = issues.get("messages") or []
        errors = [m for m in messages if m.get("severity") == 0]
        warnings = [m for m in messages if m.get("severity") == 1]
        infos = [m for m in messages if m.get("severity", 9) >= 2]
        info = result.get("info") or {}
        return {
            "ok": True,
            "tool": "khronos-gltf-validator",
            "tool_failed": False,
            "used_fallback": False,
            "validator_version": result.get("validatorVersion"),
            "num_errors": issues.get("numErrors", len(errors)),
            "num_warnings": issues.get("numWarnings", len(warnings)),
            "errors": errors,
            "warnings": warnings,
            "infos": infos,
            "total_triangle_count": info.get("totalTriangleCount"),
            "passed": (issues.get("numErrors", len(errors)) or 0) == 0,
            "raw_issues": issues,
        }
    # 官方失败：不做「假装通过」，标工具失败待人工。Python 只能做极浅的结构探测。
    shallow = _shallow_gltf_structure(path)
    return {
        "ok": False,
        "tool": "khronos-gltf-validator",
        "tool_failed": True,
        "used_fallback": True,
        "passed": None,
        "error": official.get("error") or official,
        "shallow": shallow,
        "note": "官方校验器失败，不得由模型替代判定；该项待人工。",
    }


def _shallow_gltf_structure(path: Path) -> dict[str, Any]:
    try:
        from pygltflib import GLTF2

        g = GLTF2().load(str(path))
        return {
            "ok": True,
            "asset": getattr(getattr(g, "asset", None), "version", None),
            "n_meshes": len(g.meshes or []),
            "n_buffers": len(g.buffers or []),
            "note": "仅结构可读性，不是规范校验。",
        }
    except Exception as e:
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}
