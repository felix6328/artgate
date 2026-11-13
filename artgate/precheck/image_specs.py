from __future__ import annotations

from pathlib import Path
from typing import Any

from PIL import Image


IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".tga", ".bmp", ".ktx2"}


def is_power_of_two(n: int) -> bool:
    return n > 0 and (n & (n - 1)) == 0


def inspect_image(path: Path) -> dict[str, Any]:
    """确定性图片规格，不经过模型。ktx2 本评测集不解码，标工具失败。"""
    suffix = path.suffix.lower()
    if suffix == ".ktx2":
        return {
            "ok": False,
            "tool_failed": True,
            "reason": "ktx2 解码未覆盖（模板允许该格式，评测集无真实样本）",
            "width": None,
            "height": None,
        }
    try:
        with Image.open(path) as im:
            w, h = im.size
            mode = im.mode
        return {
            "ok": True,
            "tool_failed": False,
            "width": w,
            "height": h,
            "max_side": max(w, h),
            "power_of_two": is_power_of_two(w) and is_power_of_two(h),
            "width_pot": is_power_of_two(w),
            "height_pot": is_power_of_two(h),
            "mode": mode,
            "format": suffix.lstrip("."),
        }
    except Exception as e:
        return {
            "ok": False,
            "tool_failed": True,
            "reason": f"无法读取图片: {type(e).__name__}: {e}",
            "width": None,
            "height": None,
        }
