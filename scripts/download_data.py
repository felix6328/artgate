#!/usr/bin/env python3
"""下载评测与演示用的公开资产，并记录许可。

Kenney：官方站点的 download-link 对非浏览器请求返回 403，因此从
GitHub 上的 CC0 再分发仓库 shorepine/kenney 做稀疏克隆。原作仍是
Kenney（kenney.nl），许可为 CC0 1.0。承诺哈希写入 manifest。

Poly Haven：官方 API https://api.polyhaven.com/ ，只拉 1K，不拉 8K 全集。
Khronos glTF-Sample-Assets：按模型各自许可，只取少量用于校验器测试，不是检索主库。
"""
from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from artgate.paths import DATA, LICENSES, MANIFEST, RAW, ensure_dirs  # noqa: E402

KENNEY_REPO = "https://github.com/shorepine/kenney.git"
KENNEY_COMMIT_EXPECTED = None  # 以实际 clone 的 HEAD 为准
KENNEY_SPARSE = [
    "3d/weapon",
    "3d/mini-dungeon",
    "3d/mini-characters",
    "3d/mini-forest",
    "3d/food",
    "3d/platformer",
    "3d/castle",
    "2d/Toon Characters",
    "ui/UI Pack",
    "icons/Game Icons",
]

# 写实项目：少量 1K 模型 + 1K 贴图。ID 是 Poly Haven 官网公开 ID。
PH_MODELS = [
    "Camera_01",
    "service_pistol",
    "bolt_action_rifle_7_62",
    "Television_01",
    "Lantern_01",
    "wine_bottles_01",
    "horse_statue_01",
    "sofa_02",
    "wooden_table_02",
    "Barrel_01",
    "decorative_book_set_01",
    "classic_laptop",
    "wall_clock",
    "ceramic_vase_01",
    "metal_office_desk",
]

# 将在运行时按类目挑选若列表失效的后备；默认用下面这些常见 ID，下载前会用 API 确认。
PH_TEXTURE_PREFER = [
    "brick_wall_001",
    "wood_floor_deck",
    "rusty_metal_03",
    "concrete_wall_001",
    "grass_lawn_001",
    "leather_red_02",
    "rock_wall_02",
    "plaster_white_01",
    "sand_01",
    "metal_plate_006",
    "roof_07",
    "fabric_pattern_05",
    "cobblestone_floor_01",
    "bark_brown_02",
    "tiles_003",
]

KHRONOS_REPO = "https://github.com/KhronosGroup/glTF-Sample-Assets.git"
KHRONOS_MODELS = [
    "Box",
    "BoxTextured",
    "BoxVertexColors",
    "Triangle",
    "Avocado",
    "DamagedHelmet",
    "BoomBox",
    "Duck",
    "Suzanne",
    "Lantern",
]

UA = {"User-Agent": "ArtGate-research/0.1 (personal project; educational; contact: local)"}


def sh(cmd, cwd=None, check=True):
    print("+", " ".join(cmd) if isinstance(cmd, list) else cmd)
    return subprocess.run(cmd, cwd=cwd, check=check)


def download_kenney():
    dest = RAW / "kenney"
    dest.parent.mkdir(parents=True, exist_ok=True)
    if (dest / "3d" / "weapon").exists() and list((dest / "3d" / "weapon").glob("*.glb")):
        print("Kenney 子集已存在，跳过克隆。")
        commit = _git_head(dest)
        return {"ok": True, "path": str(dest), "commit": commit, "skipped": True}
    if dest.exists() and not (dest / ".git").exists():
        raise SystemExit(f"{dest} 已存在但不是 git 仓库，请手动清理")
    if not (dest / ".git").exists():
        sh(["git", "clone", "--depth", "1", "--filter=blob:none", "--sparse", KENNEY_REPO, str(dest)])
    sh(["git", "sparse-checkout", "set", "--cone", *KENNEY_SPARSE], cwd=dest)
    # LICENSE 是文件，cone 模式可能漏掉
    lic = dest / "LICENSE.txt"
    if not lic.exists():
        r = subprocess.run(["git", "show", "HEAD:LICENSE.txt"], cwd=dest, capture_output=True, text=True)
        if r.returncode == 0:
            lic.write_text(r.stdout, encoding="utf-8")
    commit = _git_head(dest)
    return {"ok": True, "path": str(dest), "commit": commit, "repo": KENNEY_REPO, "sparse": KENNEY_SPARSE}


def _git_head(repo: Path) -> str:
    r = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo, capture_output=True, text=True)
    return r.stdout.strip()


def _git_date(repo: Path) -> str:
    r = subprocess.run(["git", "log", "-1", "--format=%cI"], cwd=repo, capture_output=True, text=True)
    return r.stdout.strip()


def _client():
    return httpx.Client(headers=UA, timeout=60.0, follow_redirects=True)


def _save(url: str, path: Path, client: httpx.Client) -> dict:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.stat().st_size > 0:
        return {"ok": True, "path": str(path), "skipped": True, "bytes": path.stat().st_size}
    r = client.get(url)
    r.raise_for_status()
    path.write_bytes(r.content)
    return {"ok": True, "path": str(path), "bytes": len(r.content), "url": url}


def _confirm_texture_ids(client: httpx.Client) -> list[str]:
    r = client.get("https://api.polyhaven.com/assets?t=textures")
    r.raise_for_status()
    all_tex = r.json()
    picked = []
    for i in PH_TEXTURE_PREFER:
        if i in all_tex:
            picked.append(i)
    # 若偏好 ID 变更，按类目补足到约 12–15
    if len(picked) < 12:
        by_cat = {}
        for k, v in all_tex.items():
            cat = (v.get("categories") or ["other"])[0]
            by_cat.setdefault(cat, []).append((v.get("download_count") or 0, k))
        for cat, items in by_cat.items():
            items.sort(reverse=True)
            for _, k in items[:1]:
                if k not in picked:
                    picked.append(k)
                if len(picked) >= 15:
                    break
            if len(picked) >= 15:
                break
    return picked[:15]


def _confirm_model_ids(client: httpx.Client) -> list[str]:
    r = client.get("https://api.polyhaven.com/assets?t=models")
    r.raise_for_status()
    all_m = r.json()
    picked = [i for i in PH_MODELS if i in all_m]
    return picked


def _thumb_url(asset_id: str) -> str:
    # 官方 CDN 缩略图，用于 CLIP，不把 4K 原图塞进模型
    return f"https://cdn.polyhaven.com/asset_img/primary/{asset_id}.png?width=512&height=512"


def download_polyhaven():
    dest = RAW / "polyhaven"
    dest.mkdir(parents=True, exist_ok=True)
    records = []
    with _client() as client:
        models = _confirm_model_ids(client)
        textures = _confirm_texture_ids(client)
        print(f"Poly Haven 模型 {models}")
        print(f"Poly Haven 贴图 {textures}")
        for aid in models:
            rec = _download_ph_model(client, dest, aid)
            records.append(rec)
            time.sleep(0.15)
        for aid in textures:
            rec = _download_ph_texture(client, dest, aid)
            records.append(rec)
            time.sleep(0.15)
    return records


def _ph_info(client, aid):
    r = client.get(f"https://api.polyhaven.com/info/{aid}")
    r.raise_for_status()
    return r.json()


def _ph_files(client, aid):
    r = client.get(f"https://api.polyhaven.com/files/{aid}")
    r.raise_for_status()
    return r.json()


def _download_ph_model(client, dest: Path, aid: str) -> dict:
    info = _ph_info(client, aid)
    files = _ph_files(client, aid)
    out = dest / "models" / aid
    out.mkdir(parents=True, exist_ok=True)
    (out / "info.json").write_text(json.dumps(info, ensure_ascii=False, indent=2), encoding="utf-8")
    # 1k gltf + includes
    gltf = (((files.get("gltf") or {}).get("1k") or {}).get("gltf") or {})
    downloaded = []
    if gltf.get("url"):
        # 主文件
        main_name = Path(gltf["url"]).name
        downloaded.append(_save(gltf["url"], out / "gltf" / main_name, client))
        for rel, meta in (gltf.get("include") or {}).items():
            if isinstance(meta, dict) and meta.get("url"):
                downloaded.append(_save(meta["url"], out / "gltf" / rel, client))
    # 缩略图
    try:
        downloaded.append(_save(_thumb_url(aid), out / "thumb.png", client))
    except Exception as e:
        print("thumb fail", aid, e)
    return {
        "id": aid,
        "kind": "model",
        "name": info.get("name"),
        "license": "CC0",
        "authors": info.get("authors"),
        "categories": info.get("categories"),
        "tags": info.get("tags"),
        "polycount_official": info.get("polycount"),
        "files": downloaded,
        "license_url": "https://polyhaven.com/license",
    }


def _download_ph_texture(client, dest: Path, aid: str) -> dict:
    info = _ph_info(client, aid)
    files = _ph_files(client, aid)
    out = dest / "textures" / aid
    out.mkdir(parents=True, exist_ok=True)
    (out / "info.json").write_text(json.dumps(info, ensure_ascii=False, indent=2), encoding="utf-8")
    downloaded = []
    # 常见通道：优先 1k jpg（更小）
    channel_keys = {
        "albedo": ["Diffuse", "diff", "diff_1k", "Diffuse_1k", "albedo"],
        "normal": ["nor_gl", "Nor_gl", "normal", "Normal"],
        "roughness": ["Rough", "rough", "Roughness"],
        "metallic": ["Metal", "metal", "Metallic"],
        "ao": ["AO", "ao", "AmbientOcclusion"],
    }
    # files 顶层键就是通道名
    lower = {k.lower(): k for k in files}
    got_channels = {}
    for ch, aliases in channel_keys.items():
        raw_key = None
        for a in aliases:
            if a in files:
                raw_key = a
                break
            if a.lower() in lower:
                raw_key = lower[a.lower()]
                break
        if not raw_key:
            continue
        entry = files[raw_key]
        # entry: { "1k": { "jpg": {url}, "png": {url} } }
        k1 = entry.get("1k") or {}
        filemeta = k1.get("jpg") or k1.get("png") or k1.get("jpeg")
        if not filemeta:
            continue
        url = filemeta.get("url") if isinstance(filemeta, dict) else None
        if not url:
            continue
        ext = Path(url).suffix
        destp = out / f"{aid}_{ch}_1k{ext}"
        downloaded.append(_save(url, destp, client))
        got_channels[ch] = destp.name
    try:
        downloaded.append(_save(_thumb_url(aid), out / "thumb.png", client))
    except Exception as e:
        print("thumb fail", aid, e)
    return {
        "id": aid,
        "kind": "texture",
        "name": info.get("name"),
        "license": "CC0",
        "authors": info.get("authors"),
        "categories": info.get("categories"),
        "tags": info.get("tags"),
        "channels": got_channels,
        "files": downloaded,
        "license_url": "https://polyhaven.com/license",
    }


def download_khronos():
    dest = RAW / "khronos-gltf-sample-assets"
    dest.parent.mkdir(parents=True, exist_ok=True)
    if not (dest / ".git").exists():
        sh(["git", "clone", "--depth", "1", "--filter=blob:none", "--sparse", KHRONOS_REPO, str(dest)])
    # 模型目录可能在 Models/Name 或 Models/Name/glTF-Binary
    existing = []
    # 先拉 Models 列表
    models_dir_ok = True
    try:
        sh(["git", "sparse-checkout", "set", "--cone", "Models", "LICENSES", "README.md"], cwd=dest)
    except subprocess.CalledProcessError:
        models_dir_ok = False
    # cone + Models 会拉全部模型，可能偏大。再收窄。
    paths = ["LICENSES", "README.md"]
    # 探测实际存在的模型名
    available = []
    r = subprocess.run(["git", "ls-tree", "-d", "--name-only", "HEAD:Models"], cwd=dest, capture_output=True, text=True)
    if r.returncode == 0:
        available = [ln.strip() for ln in r.stdout.splitlines() if ln.strip()]
    print("Khronos Models available (head):", available[:20], "total", len(available))
    want = []
    lower_map = {n.lower(): n for n in available}
    for m in KHRONOS_MODELS:
        if m in available:
            want.append(m)
        elif m.lower() in lower_map:
            want.append(lower_map[m.lower()])
    if not want and available:
        # 至少拿几个小的
        for cand in ["Box", "Triangle", "BoxTextured", "Avocado", "DamagedHelmet"]:
            if cand in available:
                want.append(cand)
    print("Khronos selected:", want)
    sparse = ["LICENSES"] + [f"Models/{m}" for m in want]
    sh(["git", "sparse-checkout", "set", "--cone", *sparse], cwd=dest)
    commit = _git_head(dest)
    date = _git_date(dest)
    # 收集每个模型的许可
    licenses = []
    for m in want:
        md = dest / "Models" / m / "README.md"
        lic = ""
        if md.exists():
            text = md.read_text(encoding="utf-8", errors="replace")
            lic = text[:2000]
        licenses.append({"model": m, "readme": str(md) if md.exists() else None, "readme_excerpt": lic})
    return {
        "ok": True,
        "path": str(dest),
        "commit": commit,
        "date": date,
        "repo": KHRONOS_REPO,
        "models": want,
        "licenses": licenses,
    }


def write_licenses(kenney, ph_records, khronos):
    DATA.mkdir(parents=True, exist_ok=True)
    k_commit = kenney.get("commit")
    k_date = _git_date(RAW / "kenney") if (RAW / "kenney" / ".git").exists() else ""
    lines = [
        "# ArtGate 所用公开资产许可清单",
        "",
        "本项目**不使用**未授权商业游戏资产，也不声称来自腾讯或任何游戏项目组。",
        "",
        "## Kenney Game Assets",
        "",
        "- 原作者：Kenney（https://kenney.nl/ ），官方资产页声明为 **CC0 1.0**（商业可用、不强制署名）。以 https://kenney.nl/support 与各资源包页面为准。",
        "- 本仓库获取方式：因 kenney.nl 的 `download-link` 接口对非浏览器请求返回 403，改从 CC0 再分发仓库",
        f"  `{KENNEY_REPO}` 稀疏克隆所选子集。提交 `{k_commit}` （提交时间 {k_date}）。",
        "- 再分发仓库的 LICENSE.txt 同样声明 CC0，并建议支持 https://kenney.nl/donate 。",
        "- 选用子集：" + ", ".join(KENNEY_SPARSE),
        "- 入库与评测时每条记录保留 source=kenney 与 pack 名。",
        "",
        "## Poly Haven",
        "",
        "- 许可：**CC0**（https://polyhaven.com/license ）。",
        "- 获取方式：官方公开 API https://api.polyhaven.com/ ，只下载 **1K** 资源与官方缩略图，不下 8K 全集。",
        "- 条目：",
    ]
    for rec in ph_records:
        authors = rec.get("authors") or {}
        if isinstance(authors, dict):
            author_s = ", ".join(f"{k} ({v})" for k, v in authors.items())
        else:
            author_s = str(authors)
        lines.append(
            f"  - `{rec.get('id')}`（{rec.get('kind')}，{rec.get('name')}），作者：{author_s}，CC0。"
        )
    lines += [
        "",
        "## Khronos glTF-Sample-Assets",
        "",
        f"- 仓库：{KHRONOS_REPO} 提交 `{khronos.get('commit')}` （{khronos.get('date')}）。",
        "- **按模型各自许可**（多为 CC-BY 等），不是检索主库，只用于 Validator / 工具链测试。",
        "- 使用前已读各模型目录 README。摘要：",
        "",
    ]
    for lic in khronos.get("licenses") or []:
        lines.append(f"### {lic['model']}")
        lines.append("")
        lines.append("```")
        lines.append((lic.get("readme_excerpt") or "（无 README）")[:1500])
        lines.append("```")
        lines.append("")
    lines += [
        "## 本项目自己写的故意损坏测试资产",
        "",
        "位于 `data/broken/`，由 `scripts/create_broken_assets.py` 从上述 CC0 资产派生，仅用于预检评测，不作为可检索库内容对外分发为「原作」。",
        "",
        "## 开源组件许可",
        "",
        "- OpenCLIP：MIT（以仓库 LICENSE 为准）",
        "- LanceDB：Apache-2.0",
        "- Khronos glTF-Validator：Apache-2.0",
        "- glTF-Transform：MIT",
        "",
        "ArtGate 自身代码未 fork Immich 或其他相册产品内核。",
    ]
    LICENSES.write_text("\n".join(lines), encoding="utf-8")
    print("wrote", LICENSES)


def count_files():
    def n(p: Path, pat: str) -> int:
        return len(list(p.glob(pat))) if p.exists() else 0

    return {
        "kenney_glb": n(RAW / "kenney", "3d/**/*.glb"),
        "kenney_png": n(RAW / "kenney", "**/*.png"),
        "polyhaven_models": n(RAW / "polyhaven" / "models", "*"),
        "khronos": n(RAW / "khronos-gltf-sample-assets" / "Models", "*"),
    }


def main():
    ensure_dirs()
    RAW.mkdir(parents=True, exist_ok=True)
    kenney = download_kenney()
    ph = download_polyhaven()
    khronos = download_khronos()
    write_licenses(kenney, ph, khronos)
    manifest = {
        "generated_by": "scripts/download_data.py",
        "kenney": kenney,
        "polyhaven": [
            {k: v for k, v in r.items() if k != "files"} | {"n_files": len(r.get("files") or [])}
            for r in ph
        ],
        "khronos": {k: v for k, v in khronos.items() if k != "licenses"},
        "counts": count_files(),
    }
    MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print("wrote", MANIFEST)
    print("counts", manifest["counts"])


if __name__ == "__main__":
    main()
