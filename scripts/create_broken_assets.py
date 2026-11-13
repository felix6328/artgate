#!/usr/bin/env python3
"""人工注入错误，生成预检金标。标签在注入时写定，不根据预检输出回改。"""
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

import yaml
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from artgate.paths import BROKEN, EVAL, RAW, ensure_dirs  # noqa: E402

KENNEY = RAW / "kenney"
PH = RAW / "polyhaven"
KHR = RAW / "khronos-gltf-sample-assets"
GOLD = EVAL / "gold_precheck.yaml"


def _copy_glb_with_textures(src: Path, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dest)
    tex = src.parent / "Textures"
    if tex.exists():
        dst_tex = dest.parent / "Textures"
        if dst_tex.exists():
            shutil.rmtree(dst_tex)
        shutil.copytree(tex, dst_tex)


def _label(item_id, path, project, asset_type, canonical, overall, expected, should_block, note, extra=None):
    d = {
        "id": item_id,
        "path": str(Path(path).relative_to(ROOT)) if Path(path).is_absolute() else str(path),
        "project_id": project,
        "asset_type": asset_type,
        "canonical_name": canonical,
        "expected_overall": overall,
        "expected": expected,
        "should_block": should_block,
        "note": note,
    }
    if extra:
        d.update(extra)
    return d


def make_bad_name():
    src = KENNEY / "3d/mini-dungeon/weapon-sword.glb"
    dest = BROKEN / "bad_name" / "final_final2.glb"
    _copy_glb_with_textures(src, dest)
    return _label(
        "bad_name_final_final2",
        dest,
        "stylized_mobile",
        "weapon",
        "final_final2.glb",
        "block",
        [
            {"check_id": "naming", "status": "fail", "severity": "block"},
            {"check_id": "gltf_valid", "status": "pass"},
        ],
        True,
        "故意使用 final_final2.glb 这种不合规命名。内容本身是合法 Kenney 剑。",
    )


def make_npot_image():
    dest = BROKEN / "npot" / "m_tex_wallpaint_lod0_v001.png"
    dest.parent.mkdir(parents=True, exist_ok=True)
    im = Image.new("RGB", (1000, 800), (170, 110, 80))
    dr = ImageDraw.Draw(im)
    dr.rectangle([50, 50, 950, 750], outline=(40, 30, 20), width=8)
    dr.text((80, 360), "NPOT 1000x800", fill=(255, 255, 255))
    im.save(dest)
    return _label(
        "npot_1000x800_texture",
        dest,
        "stylized_mobile",
        "texture",  # 模板对 texture 强制 POT
        dest.name,
        "block",
        [
            {"check_id": "naming", "status": "pass", "severity": "block"},
            {"check_id": "image_power_of_two", "status": "fail", "severity": "block"},
            {"check_id": "image_max_side", "status": "pass", "severity": "block"},
        ],
        True,
        "1000×800 非 2 的幂次，且类型为 texture，模板 M 强制 POT。",
    )


def make_npot_ui_should_not_block():
    """产品判断：UI 不强制 POT。同尺寸图若类型是 ui，不应因 POT 被 block。"""
    dest = BROKEN / "npot_ui" / "m_ui_bannerwide_lod0_v001.png"
    dest.parent.mkdir(parents=True, exist_ok=True)
    im = Image.new("RGBA", (1000, 800), (40, 80, 140, 255))
    ImageDraw.Draw(im).rounded_rectangle([20, 200, 980, 600], radius=20, fill=(50, 110, 190, 255))
    im.save(dest)
    return _label(
        "npot_ui_not_required",
        dest,
        "stylized_mobile",
        "ui",
        dest.name,
        "pass",
        [
            {"check_id": "naming", "status": "pass"},
            {"check_id": "image_power_of_two", "status": "skip"},  # 不强制，跳过拦截
            {"check_id": "image_max_side", "status": "pass"},
        ],
        False,
        "同一张 1000×800，类型为 UI，模板不强制 POT，不应因此阻断。验证产品策略而不是漏检。",
    )


def make_overbudget():
    import trimesh

    dest = BROKEN / "overbudget" / "m_prp_megaball_lod0_v001.glb"
    dest.parent.mkdir(parents=True, exist_ok=True)
    # icosphere subdiv 5 = 20 * 4^5 = 20480 三角形，超过模板 M 默认 2000
    mesh = trimesh.creation.icosphere(subdivisions=5)
    mesh.export(str(dest))
    # 记录实际面数到注记，金标只要求 poly_budget fail
    n = len(mesh.faces)
    return _label(
        "overbudget_icosphere",
        dest,
        "stylized_mobile",
        "prop",
        dest.name,
        "block",
        [
            {"check_id": "naming", "status": "pass"},
            {"check_id": "poly_budget", "status": "fail", "severity": "block"},
        ],
        True,
        f"用 trimesh icosphere(subdivisions=5) 生成约 {n} 三角面，超过模板 M prop LOD0 预算 2000。面数以工具实测为准。",
        extra={"injected_face_count": int(n)},
    )


def make_invalid_gltf():
    dest = BROKEN / "invalid_gltf" / "m_prp_brokenmesh_lod0_v001.gltf"
    dest.parent.mkdir(parents=True, exist_ok=True)
    # 引用不存在的 accessor，官方校验器应报 error
    dest.write_text(
        json.dumps({
            "asset": {"version": "2.0"},
            "scenes": [{"nodes": [0]}],
            "scene": 0,
            "nodes": [{"mesh": 0}],
            "meshes": [{"primitives": [{"attributes": {"POSITION": 99}}]}],
        }, indent=2),
        encoding="utf-8",
    )
    return _label(
        "invalid_gltf_missing_accessor",
        dest,
        "stylized_mobile",
        "prop",
        dest.name,
        "block",
        [
            {"check_id": "naming", "status": "pass"},
            {"check_id": "gltf_valid", "status": "fail", "severity": "block"},
        ],
        True,
        "故意缺失 accessor 99。只有官方校验器的 error 才应 block；本条是真正的规范错误。",
    )


def make_name_mismatch():
    src = KENNEY / "3d/mini-dungeon/weapon-sword.glb"
    dest = BROKEN / "name_mismatch" / "m_wpn_shieldround_lod0_v001.glb"
    _copy_glb_with_textures(src, dest)
    return _label(
        "name_mismatch_shield_is_sword",
        dest,
        "stylized_mobile",
        "weapon",
        dest.name,
        "warn",  # 规则层应通过；VLM mock 给 warn。无 VLM 时 overall 可能是 pass
        [
            {"check_id": "naming", "status": "pass"},
            {"check_id": "format", "status": "pass"},
            {"check_id": "gltf_valid", "status": "pass"},
            {"check_id": "poly_budget", "status": "pass"},
            # 视觉项：仅在 mock/真实 VLM 运行时期望 fail。规则层评测不把这项算进去（layer=visual）
            {"check_id": "name_content_mismatch", "status": "fail", "severity": "warn", "layer": "visual"},
        ],
        False,  # 不应被规则层 block
        "文件名是盾、内容是剑。规则层无法判定，应由 VLM 给 warn。无 API 时视觉项 not_run，规则层应 overall=pass。",
        extra={"visual_only": True, "mock_stem": "name_mismatch_shield_is_sword"},
    )


def make_wrong_format():
    dest = BROKEN / "wrong_format" / "m_prp_secretasset_lod0_v001.fbx"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(b"FBX dummy - not a real Autodesk file, only for extension check\n")
    return _label(
        "wrong_format_fbx",
        dest,
        "stylized_mobile",
        "prop",
        dest.name,
        "block",
        [
            {"check_id": "naming", "status": "fail"},  # .fbx 不匹配命名正则里的扩展名
            {"check_id": "format", "status": "fail", "severity": "block"},
        ],
        True,
        "模板 M 不允许 fbx。命名正则也不含该扩展名。",
    )


def make_oversized():
    dest = BROKEN / "oversized" / "m_tex_hugemap_lod0_v001.png"
    dest.parent.mkdir(parents=True, exist_ok=True)
    # 模板 M 上限 8MB。写一张能超过 8MB 的 PNG（大尺寸、低压缩）
    # 2048 上限会先卡最长边；用 2048 但把文件体积做大：追加随机块会破坏 PNG。
    # 改用合法 PNG + 体积：2048x2048 RGBA 未压缩级大约 > 8MB。
    im = Image.new("RGBA", (2048, 2048), (10, 20, 30, 255))
    # 加入噪声提高不可压缩性
    import os

    px = im.load()
    # 不要逐像素 Python 循环太慢：用随机字节经 frombytes 不够对齐。直接保存后若不足 8MB，另写 raw。
    im.save(dest, format="PNG", compress_level=0)
    if dest.stat().st_size <= 8 * 1024 * 1024:
        # 在文件尾追加注释块以外的填充会坏掉 PNG 头检查；改用合法 tEXt 不够大。
        # 用 max_file_size 检查的是字节数，图片规格仍应可读。PIL 打开只读 IHDR。
        # 保守做法：单独做一条「超体积」用 .glb 填充。
        pass
    size = dest.stat().st_size
    # 若仍不足 8MB，改走 glb 填充路径
    if size <= 8 * 1024 * 1024:
        dest = BROKEN / "oversized" / "m_prp_hugepack_lod0_v001.glb"
        src = KENNEY / "3d/mini-dungeon/weapon-sword.glb"
        data = src.read_bytes() if src.exists() else b"glTF" + b"\x00" * 100
        # 合法 GLB 后面追加数据可能让校验器报错。体积检查在校验之前也会跑。
        # 为让体积成为确定的 block 项：写纯填充文件但扩展名 png，同时 image 工具可能失败。
        # 更干净：生成 4096x4096 会同时触达 max_side（M 上限 2048）。我们再做一个只超体积的。
        dest.write_bytes(data + os.urandom(9 * 1024 * 1024))
        return _label(
            "oversized_file",
            dest,
            "stylized_mobile",
            "prop",
            dest.name,
            "block",
            [
                {"check_id": "file_size", "status": "fail", "severity": "block"},
            ],
            True,
            "在合法剑模型后附加随机字节使体积超过模板 M 的 8MB。校验器可能同时报错；金标只强制 file_size=fail，其它项不作为本条必测。",
            extra={"loose_other_checks": True},
        )
    return _label(
        "oversized_file",
        dest,
        "stylized_mobile",
        "texture",
        dest.name,
        "block",
        [{"check_id": "file_size", "status": "fail", "severity": "block"}],
        True,
        "体积超过模板 M 的 8MB。",
        extra={"loose_other_checks": True},
    )


def make_overside():
    dest = BROKEN / "overside" / "m_tex_toobig_lod0_v001.png"
    dest.parent.mkdir(parents=True, exist_ok=True)
    # 4096 是 2 的幂次，模板 M 上限 2048，应因 max_side block，不应因 POT block
    im = Image.new("RGB", (4096, 4096), (90, 90, 90))
    im.save(dest, format="PNG", compress_level=3)
    return _label(
        "over_max_side_4096",
        dest,
        "stylized_mobile",
        "texture",
        dest.name,
        "block",
        [
            {"check_id": "naming", "status": "pass"},
            {"check_id": "image_power_of_two", "status": "pass"},
            {"check_id": "image_max_side", "status": "fail", "severity": "block"},
        ],
        True,
        "4096×4096 是 2 的幂次，但超过模板 M 贴图上限 2048。用来区分两项检查。",
    )


def make_compliant_samples():
    items = []
    samples = [
        (KENNEY / "3d/mini-dungeon/weapon-sword.glb", "weapon", "sword", "stylized_mobile"),
        (KENNEY / "3d/mini-dungeon/shield-round.glb", "weapon", "shieldround", "stylized_mobile"),
        (KENNEY / "3d/mini-dungeon/character-human.glb", "character", "human", "stylized_mobile"),
        (KENNEY / "3d/food/apple.glb", "prop", "apple", "stylized_mobile"),
        (KENNEY / "3d/mini-forest/tree.glb", "environment", "tree", "stylized_mobile"),
    ]
    from artgate.config import load_template, make_canonical

    for src, atype, stem, proj in samples:
        if not src.exists():
            continue
        tmpl = load_template(proj)
        name = make_canonical(tmpl, atype, stem, "glb", lod=0)
        dest = BROKEN / "compliant" / name
        _copy_glb_with_textures(src, dest)
        items.append(_label(
            f"compliant_{stem}",
            dest,
            proj,
            atype,
            name,
            "pass",
            [
                {"check_id": "naming", "status": "pass"},
                {"check_id": "format", "status": "pass"},
                {"check_id": "file_size", "status": "pass"},
                {"check_id": "gltf_valid", "status": "pass"},
                {"check_id": "poly_budget", "status": "pass"},
                {"check_id": "texture_power_of_two_3d", "status": "pass"},
            ],
            False,
            f"合规对照样本，来自 Kenney {src.name}，已赋规范文件名。",
        ))
    # 一张合规 POT 贴图
    dest = BROKEN / "compliant" / "m_tex_colormapref_lod0_v001.png"
    dest.parent.mkdir(parents=True, exist_ok=True)
    src_tex = KENNEY / "3d/mini-dungeon/Textures/colormap.png"
    if src_tex.exists():
        shutil.copy2(src_tex, dest)
        items.append(_label(
            "compliant_colormap",
            dest,
            "stylized_mobile",
            "texture",
            dest.name,
            "pass",
            [
                {"check_id": "naming", "status": "pass"},
                {"check_id": "image_power_of_two", "status": "pass"},
                {"check_id": "image_max_side", "status": "pass"},
            ],
            False,
            "Kenney colormap 512×512，合规 POT 贴图对照。",
        ))
    return items


def make_style_drift():
    # 写实缩略图以规范的 M 命名提交到风格化项目
    thumbs = list((PH / "models").glob("*/thumb.png")) if PH.exists() else []
    if not thumbs:
        return None
    src = thumbs[0]
    dest = BROKEN / "style_drift" / "m_prp_camerafancy_lod0_v001.png"
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dest)
    # PNG 作为 prop 提交：UI/prop 不强制 POT；可能因尺寸通过规则
    return _label(
        "style_drift_realistic_in_stylized",
        dest,
        "stylized_mobile",
        "prop",
        dest.name,
        "warn",
        [
            {"check_id": "naming", "status": "pass"},
            {"check_id": "style_drift", "status": "fail", "severity": "warn", "layer": "visual"},
        ],
        False,
        "把 Poly Haven 写实缩略图用风格化模板的规范名提交。规则层不应 block；VLM mock 给风格漂移 warn。",
        extra={"visual_only": True, "mock_stem": "style_drift_realistic_in_stylized", "source_thumb": str(src)},
    )


def make_npot_3d_texture():
    """带 1000x800 贴图的简单 glTF，用于 3D 贴图 POT 检查。"""
    dest_dir = BROKEN / "npot_3d"
    dest_dir.mkdir(parents=True, exist_ok=True)
    tex = dest_dir / "albedo.png"
    Image.new("RGB", (1000, 800), (200, 40, 40)).save(tex)
    dest = dest_dir / "m_prp_redquad_lod0_v001.gltf"
    # 最小带外部贴图的三角片。用 pygltflib 更稳，这里手写一个有效结构 + 外部 png。
    # 若手写容易无效，改用 trimesh。
    import numpy as np
    import trimesh

    verts = np.array([[0, 0, 0], [1, 0, 0], [1, 1, 0], [0, 1, 0]], dtype=np.float32)
    faces = np.array([[0, 1, 2], [0, 2, 3]], dtype=np.int64)
    uv = np.array([[0, 0], [1, 0], [1, 1], [0, 1]], dtype=np.float32)
    mesh = trimesh.Trimesh(vertices=verts, faces=faces, process=False)
    mat = trimesh.visual.material.PBRMaterial(baseColorTexture=Image.open(tex))
    mesh.visual = trimesh.visual.TextureVisuals(uv=uv, material=mat)
    glb_dest = dest_dir / "m_prp_redquad_lod0_v001.glb"
    mesh.export(str(glb_dest))
    return _label(
        "npot_3d_texture",
        glb_dest,
        "stylized_mobile",
        "prop",
        glb_dest.name,
        "block",
        [
            {"check_id": "naming", "status": "pass"},
            {"check_id": "texture_power_of_two_3d", "status": "fail", "severity": "block"},
        ],
        True,
        "网格面数很低，但贴图为 1000×800。应被 3D 贴图 POT 规则拦截，而不是面数规则。",
    )


def make_khronos_valid():
    # 找一个小的官方样本，只做校验器通过对照。不进检索主库。
    candidates = [
        KHR / "Models" / "Box" / "glTF-Binary" / "Box.glb",
        KHR / "Models" / "Triangle" / "glTF" / "Triangle.gltf",
        KHR / "Models" / "BoxTextured" / "glTF-Binary" / "BoxTextured.glb",
    ]
    src = next((p for p in candidates if p.exists()), None)
    if src is None:
        # 再搜一下
        found = list((KHR / "Models").glob("Box/**/*.glb")) if (KHR / "Models").exists() else []
        src = found[0] if found else None
    if src is None:
        return None
    dest = BROKEN / "khronos_valid" / src.name
    dest.parent.mkdir(parents=True, exist_ok=True)
    # 复制整个模型目录以保留外部资源
    src_dir = src.parent
    dst_dir = dest.parent / src_dir.name
    if dst_dir.exists():
        shutil.rmtree(dst_dir)
    shutil.copytree(src_dir, dst_dir)
    dest = dst_dir / src.name
    # 命名可能不合 M 规范，本条只测 gltf_valid，naming 用宽松：记录 actual name，金标不强制 naming
    return _label(
        "khronos_valid_sample",
        dest,
        "stylized_mobile",
        "prop",
        dest.name,  # 可能不合规
        "block" if not dest.name.startswith("m_") else "pass",
        [
            {"check_id": "gltf_valid", "status": "pass"},
        ],
        None,  # should_block 取决于命名；本条不计入误拦率（should_block is None）
        f"Khronos 样本 {src}，用于确认官方校验器在合规文件上通过。许可见 data/licenses.md。不计入误拦率。",
        extra={"loose_other_checks": True, "exclude_from_false_block": True, "license_note": "Khronos per-model license"},
    )


def main():
    ensure_dirs()
    BROKEN.mkdir(parents=True, exist_ok=True)
    EVAL.mkdir(parents=True, exist_ok=True)
    items = []
    makers = [
        make_bad_name,
        make_npot_image,
        make_npot_ui_should_not_block,
        make_overbudget,
        make_invalid_gltf,
        make_name_mismatch,
        make_wrong_format,
        make_oversized,
        make_overside,
        make_npot_3d_texture,
    ]
    for fn in makers:
        try:
            rec = fn()
            if rec:
                items.append(rec)
                print("ok", rec["id"], rec["path"])
        except Exception as e:
            print("FAIL", fn.__name__, type(e), e)
    try:
        items.extend(make_compliant_samples())
        print("ok compliant samples")
    except Exception as e:
        print("FAIL compliant", e)
    try:
        rec = make_style_drift()
        if rec:
            items.append(rec)
            print("ok", rec["id"])
        else:
            print("skip style_drift (Poly Haven 尚未下载)")
    except Exception as e:
        print("FAIL style_drift", e)
    try:
        rec = make_khronos_valid()
        if rec:
            items.append(rec)
            print("ok", rec["id"])
        else:
            print("skip khronos_valid")
    except Exception as e:
        print("FAIL khronos", e)

    gold = {
        "status": "authored_with_injection",
        "note": (
            "预检金标在注入错误时写定，不根据预检脚本输出回改。"
            "layer=visual 的期望只在 VLM 实际运行（含 mock）时评估；规则层 Precision/Recall 排除这些项。"
            "should_block=false 的样本用于误拦率。exclude_from_false_block 的样本不计入误拦率。"
        ),
        "items": items,
    }
    GOLD.write_text(yaml.safe_dump(gold, allow_unicode=True, sort_keys=False), encoding="utf-8")
    print("wrote", GOLD, "n=", len(items))


if __name__ == "__main__":
    main()
