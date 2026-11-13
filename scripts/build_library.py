#!/usr/bin/env python3
"""扫描公开资产子集 → 赋类型与规范名 → 渲染预览 → 预检 → 种子确认入库 → 嵌入索引。

种子库状态为 approved，元数据写明「模拟已在生产库的历史资产」，不是跳过门禁。
故意损坏资产不进入可检索库，只进入评测与（可选）演示队列。
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

from tqdm import tqdm

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from artgate.config import load_template, make_canonical  # noqa: E402
from artgate.db import add_review, init_schema  # noqa: E402
from artgate.ingest.importer import ingest_file  # noqa: E402
from artgate.paths import CATALOG, DATA, RAW, ensure_dirs  # noqa: E402

KENNEY = RAW / "kenney"
PH = RAW / "polyhaven"

WEAPON_KEYS = (
    "weapon", "sword", "spear", "bow", "arrow", "shield", "pistol", "knife",
    "grenade", "shotgun", "sniper", "uzi", "machinegun", "flamethrower",
    "rocket", "siege", "ballista", "catapult", "trebuchet", "rifle", "ammo_",
)
ENV_KEYS = (
    "tree", "plant", "rock", "grass", "floor", "wall", "tower", "bridge",
    "building", "ground", "dirt", "stones", "patch-", "stairs", "column",
    "gate", "fence", "platform", "hills",
)


def infer_type(path: Path, pack: str) -> str:
    s = f"{path.as_posix()} {pack}".lower()
    name = path.stem.lower()
    if "ui pack" in s or "game icons" in s:
        return "ui"
    if "toon characters" in s or name.startswith("character") or "character-" in name:
        return "character"
    if any(k in name for k in WEAPON_KEYS):
        return "weapon"
    if "texture" in s or "polyhaven/textures" in s:
        return "texture"
    if any(k in name for k in ENV_KEYS):
        return "environment"
    if "wheelchair" in name or "aid-" in name or name.startswith("aid_"):
        return "prop"
    return "prop"


def tags_from(path: Path, pack: str, asset_type: str) -> list[str]:
    parts = re.split(r"[-_.\s/]+", path.stem.lower())
    tags = [p for p in parts if p and p not in {"m", "r", "lod0", "v001", "glb"}]
    tags.append(asset_type)
    tags.append(pack)
    # 中英对照少量高频
    mapping = {
        "sword": "剑", "shield": "盾", "spear": "矛", "bow": "弓", "arrow": "箭",
        "apple": "苹果", "banana": "香蕉", "burger": "汉堡", "cake": "蛋糕",
        "tree": "树", "chest": "宝箱", "coin": "金币", "barrel": "桶",
        "pistol": "手枪", "sniper": "狙击", "grenade": "手榴弹",
        "character": "角色", "orc": "兽人", "human": "人类",
        "archer": "弓箭手", "tent": "帐篷", "button": "按钮",
        "trophy": "奖杯", "star": "星星", "gamepad": "手柄",
        "camera": "相机", "sofa": "沙发", "rifle": "步枪",
    }
    for t in list(tags):
        if t in mapping:
            tags.append(mapping[t])
    return sorted(set(tags))


def select_kenney_3d() -> list[Path]:
    root = KENNEY / "3d"
    out = []
    for p in sorted(root.rglob("*.glb")):
        rel = p.relative_to(root).as_posix()
        name = p.name
        pack = p.parent.name
        if pack == "Textures":
            continue
        if "platformer" in rel and (name.startswith("block-grass") or name.startswith("block-snow")):
            continue
        if "castle" in rel and (
            name.startswith("tower-square-mid") or name.startswith("tower-hexagon-mid")
            or name.startswith("tower-square-top-roof")
        ):
            continue
        out.append(p)
    return out


def select_kenney_2d() -> list[Path]:
    out = []
    # Toon Characters: 仅 Poses（非 HD、非 Parts）
    tc = KENNEY / "2d" / "Toon Characters"
    if tc.exists():
        for p in sorted(tc.rglob("*.png")):
            parts = {x.lower() for x in p.parts}
            if "poses" in parts and "poses hd" not in {x.lower() for x in p.parent.parts} and "HD" not in p.parent.name:
                # 排除 Poses HD 目录
                if "poses hd" in p.as_posix().lower():
                    continue
                out.append(p)
    # UI Pack: 只取 Blue 一层，不要 Double、不要其它颜色
    ui = KENNEY / "ui" / "UI Pack" / "Blue"
    if ui.exists():
        for p in sorted(ui.glob("*.png")):
            out.append(p)
    extra = KENNEY / "ui" / "UI Pack" / "Extra"
    if extra.exists():
        for p in sorted(extra.glob("*.png")):
            out.append(p)
    # Game Icons Black 1x
    gi = KENNEY / "icons" / "Game Icons" / "Black" / "1x"
    if gi.exists():
        for p in sorted(gi.glob("*.png")):
            out.append(p)
    return out


def select_polyhaven() -> list[tuple[Path, Path | None, str, str, dict]]:
    """返回 (file, preview, asset_type, pack, info)."""
    rows = []
    models = PH / "models"
    if models.exists():
        for d in sorted(models.iterdir()):
            if not d.is_dir():
                continue
            gltfs = list((d / "gltf").glob("*.gltf")) + list((d / "gltf").glob("*.glb"))
            # 主文件通常是 *_1k.gltf
            main = None
            for g in gltfs:
                if g.suffix == ".gltf":
                    main = g
                    break
            if main is None and gltfs:
                main = gltfs[0]
            thumb = d / "thumb.png"
            info = {}
            ip = d / "info.json"
            if ip.exists():
                info = json.loads(ip.read_text(encoding="utf-8"))
            if main:
                atype = "weapon" if any(x in d.name.lower() for x in ("pistol", "rifle", "gun")) else "prop"
                if "tree" in d.name.lower() or "grass" in d.name.lower():
                    atype = "environment"
                if "sofa" in d.name.lower() or "chair" in d.name.lower() or "desk" in d.name.lower() or "table" in d.name.lower():
                    atype = "prop"
                rows.append((main, thumb if thumb.exists() else None, atype, f"polyhaven-model:{d.name}", info))
    textures = PH / "textures"
    if textures.exists():
        for d in sorted(textures.iterdir()):
            if not d.is_dir():
                continue
            # 用 albedo / 否则任意 png/jpg + thumb
            files = list(d.glob("*_albedo_*")) or list(d.glob("*_diff_*")) or list(d.glob("*.jpg")) + list(d.glob("*.png"))
            files = [f for f in files if f.name != "thumb.png"]
            thumb = d / "thumb.png"
            info = {}
            ip = d / "info.json"
            if ip.exists():
                info = json.loads(ip.read_text(encoding="utf-8"))
            if files:
                rows.append((files[0], thumb if thumb.exists() else files[0], "texture", f"polyhaven-texture:{d.name}", {**info, "companion": [str(x) for x in files]}))
    return rows


def ingest_one(
    src: Path,
    project_id: str,
    asset_type: str,
    source: str,
    pack: str,
    license_name: str,
    *,
    preview: Path | None = None,
    description: str = "",
    extra_tags: list[str] | None = None,
    companion=None,
    metadata=None,
    auto_status="approved",
    skip_vlm=True,
) -> dict:
    tmpl = load_template(project_id)
    canon = make_canonical(tmpl, asset_type, src.stem, src.suffix, lod=0)
    tags = tags_from(src, pack, asset_type) + (extra_tags or [])
    result = ingest_file(
        src,
        project_id,
        asset_type=asset_type,
        source=source,
        source_pack=pack,
        license_name=license_name,
        tags=tags,
        description=description,
        original_filename=src.name,
        canonical_name=canon,
        copy=False,  # 种子库直接引用 raw，避免再拷一份
        preview_src=preview,
        auto_status=auto_status,
        skip_vlm=skip_vlm,
        companion_files=companion,
        metadata={
            "seed": True,
            "seed_reason": "模拟已在生产库的历史资产，预检已跑，确认动作是 seed_approve",
            **(metadata or {}),
        },
        uploader="seed",
        index=False,
    )
    if auto_status == "approved":
        add_review(
            result["asset_id"],
            "pass",
            "seed_approve：模拟已在生产库的历史资产。预检报告已保存。不是跳过门禁。",
            "seed",
            "pending",
            "approved",
        )
    return result


def batch_index(batch_size: int = 16):
    from pathlib import Path
    from artgate.db import list_assets
    from artgate.search import embedder
    from artgate.search import index as vecindex
    from tqdm import tqdm as _tqdm

    assets = [a for a in list_assets(status="approved") if a.get("preview_path") and Path(a["preview_path"]).exists()]
    # also appeal_passed — none at seed time
    if not assets:
        return 0, ["no approved assets with previews"]
    paths = [Path(a["preview_path"]) for a in assets]
    vecs = embedder.embed_images(paths)
    dim = vecs.shape[1]
    rows = []
    for a, v in zip(assets, vecs):
        rows.append({
            "asset_id": a["id"],
            "vector": v,
            "project_id": a.get("project_id"),
            "asset_type": a.get("asset_type"),
            "format": a.get("format"),
            "triangles": a.get("triangles") or 0,
            "canonical_name": a.get("canonical_name"),
            "original_filename": a.get("original_filename"),
            "tags": a.get("tags") or [],
            "description": a.get("description") or "",
            "preview_path": a.get("preview_path"),
            "source": a.get("source"),
            "license": a.get("license"),
            "status": a.get("status"),
        })
    # upsert in chunks
    n = 0
    errs = []
    for i in range(0, len(rows), 128):
        try:
            n += vecindex.upsert_vectors(rows[i:i+128], dim=dim)
        except Exception as e:
            errs.append(f"{type(e).__name__}: {e}")
    return n, errs



def main():
    ensure_dirs()
    init_schema()
    catalog = []
    errors = []

    k3d = select_kenney_3d()
    k2d = select_kenney_2d()
    print(f"Kenney 3D selected {len(k3d)}, 2D selected {len(k2d)}")

    for p in tqdm(k3d, desc="Kenney 3D"):
        pack = p.parent.name
        atype = infer_type(p, pack)
        try:
            r = ingest_one(
                p, "stylized_mobile", atype, "kenney", pack, "CC0 (Kenney)",
                description=f"Kenney {pack} / {p.stem}",
            )
            catalog.append(_cat(r, p))
        except Exception as e:
            errors.append({"path": str(p), "error": f"{type(e).__name__}: {e}"})

    for p in tqdm(k2d, desc="Kenney 2D"):
        # pack 用更有意义的相对段
        try:
            rel = p.relative_to(KENNEY)
            pack = "/".join(rel.parts[:2])
        except ValueError:
            pack = p.parent.name
        atype = infer_type(p, pack)
        try:
            r = ingest_one(
                p, "stylized_mobile", atype, "kenney", pack, "CC0 (Kenney)",
                preview=p,
                description=f"Kenney {pack} / {p.stem}",
            )
            catalog.append(_cat(r, p))
        except Exception as e:
            errors.append({"path": str(p), "error": f"{type(e).__name__}: {e}"})

    ph_rows = select_polyhaven()
    print(f"Poly Haven selected {len(ph_rows)}")
    for src, preview, atype, pack, info in tqdm(ph_rows, desc="Poly Haven"):
        desc = info.get("name") or src.stem
        tags = list(info.get("tags") or []) + list(info.get("categories") or [])
        authors = info.get("authors") or {}
        try:
            companion = [Path(x) for x in (info.get("companion") or []) if Path(x).exists()]
            r = ingest_one(
                src, "realistic", atype, "polyhaven", pack, "CC0 (Poly Haven)",
                preview=preview,
                description=desc,
                extra_tags=[str(t) for t in tags],
                companion=companion or None,
                metadata={"authors": authors, "polycount_official": info.get("polycount")},
            )
            catalog.append(_cat(r, src))
        except Exception as e:
            errors.append({"path": str(src), "error": f"{type(e).__name__}: {e}"})

    print("batch embedding + indexing approved assets...")
    n_idx, idx_err = batch_index()
    print("indexed", n_idx, "index_errors", idx_err)

    CATALOG.write_text(json.dumps({
        "n": len(catalog),
        "n_errors": len(errors),
        "n_indexed": n_idx,
        "assets": catalog,
        "errors": errors,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print("catalog", CATALOG, "n=", len(catalog), "errors=", len(errors))
    if errors:
        print("first errors:")
        for e in errors[:8]:
            print(" ", e)


def _cat(r: dict, src: Path) -> dict:
    a = r.get("asset") or {}
    return {
        "id": r.get("asset_id"),
        "canonical_name": r.get("canonical_name"),
        "original_filename": a.get("original_filename") or src.name,
        "original_path": str(src),
        "project_id": a.get("project_id"),
        "asset_type": a.get("asset_type"),
        "format": a.get("format"),
        "triangles": a.get("triangles"),
        "tags": a.get("tags"),
        "description": a.get("description"),
        "source": a.get("source"),
        "source_pack": a.get("source_pack"),
        "license": a.get("license"),
        "preview_path": a.get("preview_path"),
        "status": a.get("status"),
        "precheck_overall": (r.get("report") or {}).get("overall"),
    }


if __name__ == "__main__":
    main()
