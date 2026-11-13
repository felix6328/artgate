"""3D 预览：纯软件等轴测光栅化，不依赖 GPU / OpenGL。

CLIP 不能直接吃网格，必须用预览图。Kenney 包在本子集里没有逐模型官方预览，
因此自己渲染。做不出来会在 manifest 里记限制，2D 资产直接用原图缩略。
"""
from __future__ import annotations

import math
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image

from artgate.paths import PREVIEWS


def preview_path_for(asset_id: str) -> Path:
    PREVIEWS.mkdir(parents=True, exist_ok=True)
    safe = asset_id.replace(":", "_").replace("/", "_")
    return PREVIEWS / f"{safe}.png"


def make_preview(src: Path, dest: Path, size: int = 384) -> dict[str, Any]:
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    suffix = Path(src).suffix.lower()
    if suffix in {".png", ".jpg", ".jpeg", ".webp", ".bmp"}:
        im = Image.open(src).convert("RGBA")
        im = _fit_canvas(im, size, bg=(248, 249, 252, 255))
        im.convert("RGB").save(dest, "PNG")
        return {"ok": True, "method": "image-thumbnail", "path": str(dest)}
    if suffix in {".glb", ".gltf"}:
        try:
            im = render_glb(src, size=size)
            im.save(dest, "PNG")
            return {"ok": True, "method": "software-isometric", "path": str(dest)}
        except Exception as e:
            # 占位，避免整条入库失败；检索质量会差，记入限制
            ph = Image.new("RGB", (size, size), (240, 242, 246))
            ph.save(dest, "PNG")
            return {"ok": False, "method": "placeholder", "path": str(dest), "error": f"{type(e).__name__}: {e}"}
    return {"ok": False, "method": "unsupported", "error": f"不支持的预览源 {suffix}"}


def _fit_canvas(im: Image.Image, size: int, bg=(248, 249, 252, 255)) -> Image.Image:
    im = im.convert("RGBA")
    im.thumbnail((size, size), Image.Resampling.LANCZOS)
    canvas = Image.new("RGBA", (size, size), bg)
    x = (size - im.width) // 2
    y = (size - im.height) // 2
    canvas.paste(im, (x, y), im)
    return canvas


def render_glb(path: Path, size: int = 384, bg=(248, 249, 252)) -> Image.Image:
    import trimesh

    loaded = trimesh.load(str(path), force="scene", process=False)
    if not isinstance(loaded, trimesh.Scene):
        loaded = loaded.scene()
    scene: trimesh.Scene = loaded

    verts_list = []
    faces_list = []
    colors_list = []
    offset = 0
    for name, geom in scene.geometry.items():
        if not hasattr(geom, "faces") or not hasattr(geom, "vertices"):
            continue
        # world matrix
        try:
            nodes = scene.graph.nodes_geometry
            T = np.eye(4)
            for n in nodes:
                gname = scene.graph.get(n)[1] if False else None
            # trimesh: scene.graph.get(frame_to) 
        except Exception:
            T = np.eye(4)
        # Use scene.graph to get transform for this geometry
        T = _geom_transform(scene, name)
        v = np.asarray(geom.vertices, dtype=np.float64)
        ones = np.ones((len(v), 1))
        vw = (np.hstack([v, ones]) @ T.T)[:, :3]
        f = np.asarray(geom.faces, dtype=np.int64) + offset
        cols = _vertex_colors(geom)
        verts_list.append(vw)
        faces_list.append(f)
        colors_list.append(cols)
        offset += len(vw)

    if not verts_list:
        raise ValueError("场景中没有可渲染网格")

    verts = np.concatenate(verts_list, axis=0)
    faces = np.concatenate(faces_list, axis=0)
    colors = np.concatenate(colors_list, axis=0)

    # 居中并按包围盒缩放
    center = (verts.max(axis=0) + verts.min(axis=0)) / 2.0
    verts = verts - center
    extent = np.abs(verts).max() or 1.0
    verts = verts / extent

    # 等轴测：绕 Y 45°，再绕 X 35.264°
    ay = math.radians(45)
    ax = math.radians(35.264)
    Ry = np.array([[math.cos(ay), 0, math.sin(ay)], [0, 1, 0], [-math.sin(ay), 0, math.cos(ay)]])
    Rx = np.array([[1, 0, 0], [0, math.cos(ax), -math.sin(ax)], [0, math.sin(ax), math.cos(ax)]])
    R = Rx @ Ry
    pts = verts @ R.T

    # 投影到像素：x,y → 画布，z 用作深度（越大越近，右手系旋转后 y 向上）
    margin = 0.08
    xy = pts[:, :2]
    mn, mx = xy.min(axis=0), xy.max(axis=0)
    span = np.maximum(mx - mn, 1e-6)
    scale = (size * (1 - 2 * margin)) / span.max()
    origin = (mn + mx) / 2.0
    px = (pts[:, 0] - origin[0]) * scale + size / 2.0
    py = -(pts[:, 1] - origin[1]) * scale + size / 2.0  # 屏幕 y 向下
    pz = pts[:, 2]
    screen = np.stack([px, py, pz], axis=1)

    # 简单方向光
    normals = _face_normals(verts, faces)
    light = np.array([0.35, 0.7, 0.6], dtype=np.float64)
    light = light / np.linalg.norm(light)
    shade = np.clip(normals @ (R @ light), 0.15, 1.0)

    img = np.zeros((size, size, 3), dtype=np.float64)
    img[:, :] = np.array(bg, dtype=np.float64) / 255.0
    zbuf = np.full((size, size), -np.inf, dtype=np.float64)

    # 画家 + zbuffer，按深度由远到近
    face_z = screen[faces].mean(axis=1)[:, 2]
    order = np.argsort(face_z)  # 远（小）先画
    # 限制极端高模的耗时：最多 80k 三角
    if len(order) > 80000:
        order = order[:: int(np.ceil(len(order) / 80000))]

    for fi in order:
        i0, i1, i2 = faces[fi]
        t = screen[[i0, i1, i2]]
        col = (colors[i0] + colors[i1] + colors[i2]) / 3.0
        col = np.clip(col * (0.35 + 0.65 * shade[fi]), 0, 1)
        _fill_triangle(img, zbuf, t, col)

    out = (np.clip(img, 0, 1) * 255).astype(np.uint8)
    return Image.fromarray(out, "RGB")


def _geom_transform(scene, geom_name: str) -> np.ndarray:
    try:
        for node_name in scene.graph.nodes_geometry:
            transform, corresponding = scene.graph.get(frame_to=node_name)
            if corresponding == geom_name:
                return np.asarray(transform, dtype=np.float64)
    except Exception:
        pass
    return np.eye(4)


def _vertex_colors(geom) -> np.ndarray:
    n = len(geom.vertices)
    default = np.tile(np.array([[0.72, 0.74, 0.78]], dtype=np.float64), (n, 1))
    vis = getattr(geom, "visual", None)
    if vis is None:
        return default
    # vertex colors
    if getattr(vis, "kind", None) == "vertex" and getattr(vis, "vertex_colors", None) is not None:
        vc = np.asarray(vis.vertex_colors)[:, :3].astype(np.float64)
        if vc.max() > 1.5:
            vc = vc / 255.0
        return vc
    # 纹理：在顶点 UV 上采样
    mat = getattr(vis, "material", None)
    uv = getattr(vis, "uv", None)
    img = None
    if mat is not None:
        img = getattr(mat, "baseColorTexture", None) or getattr(mat, "image", None)
    if img is not None and uv is not None and len(uv) == n:
        arr = np.asarray(img.convert("RGB"), dtype=np.float64) / 255.0
        h, w = arr.shape[:2]
        u = np.clip(np.mod(uv[:, 0], 1.0), 0, 1 - 1e-6)
        v = np.clip(1.0 - np.mod(uv[:, 1], 1.0), 0, 1 - 1e-6)  # glTF v 向上
        x = (u * (w - 1)).astype(np.int32)
        y = (v * (h - 1)).astype(np.int32)
        return arr[y, x]
    # baseColorFactor
    if mat is not None and getattr(mat, "baseColorFactor", None) is not None:
        fc = np.asarray(mat.baseColorFactor, dtype=np.float64)[:3]
        if fc.max() > 1.5:
            fc = fc / 255.0
        return np.tile(fc.reshape(1, 3), (n, 1))
    return default


def _face_normals(verts: np.ndarray, faces: np.ndarray) -> np.ndarray:
    v0 = verts[faces[:, 0]]
    v1 = verts[faces[:, 1]]
    v2 = verts[faces[:, 2]]
    n = np.cross(v1 - v0, v2 - v0)
    lens = np.linalg.norm(n, axis=1, keepdims=True)
    lens = np.maximum(lens, 1e-9)
    return n / lens


def _fill_triangle(img: np.ndarray, zbuf: np.ndarray, tri: np.ndarray, color: np.ndarray) -> None:
    """tri: (3,3) x,y,z in pixel space."""
    h, w = zbuf.shape
    xs = tri[:, 0]
    ys = tri[:, 1]
    minx = max(int(np.floor(xs.min())), 0)
    maxx = min(int(np.ceil(xs.max())), w - 1)
    miny = max(int(np.floor(ys.min())), 0)
    maxy = min(int(np.ceil(ys.max())), h - 1)
    if minx > maxx or miny > maxy:
        return
    x0, y0, z0 = tri[0]
    x1, y1, z1 = tri[1]
    x2, y2, z2 = tri[2]
    denom = (y1 - y2) * (x0 - x2) + (x2 - x1) * (y0 - y2)
    if abs(denom) < 1e-9:
        return
    # 小三角形用点采样
    for py in range(miny, maxy + 1):
        for px in range(minx, maxx + 1):
            # 像素中心
            cx, cy = px + 0.5, py + 0.5
            a = ((y1 - y2) * (cx - x2) + (x2 - x1) * (cy - y2)) / denom
            b = ((y2 - y0) * (cx - x2) + (x0 - x2) * (cy - y2)) / denom
            c = 1 - a - b
            if a < 0 or b < 0 or c < 0:
                continue
            z = a * z0 + b * z1 + c * z2
            if z >= zbuf[py, px]:
                zbuf[py, px] = z
                img[py, px] = color
