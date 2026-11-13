from __future__ import annotations

import re
from copy import deepcopy
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from artgate.paths import SETTINGS_FILE, TEMPLATES


def _load_yaml(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if not isinstance(data, dict):
        raise ValueError(f"YAML 根节点必须是映射: {path}")
    return data


@lru_cache(maxsize=1)
def settings() -> dict[str, Any]:
    return _load_yaml(SETTINGS_FILE)


def template_path(project_id: str) -> Path:
    projects = settings().get("projects") or {}
    if project_id in projects:
        rel = projects[project_id]["template"]
        return (SETTINGS_FILE.parents[1] / rel).resolve() if not Path(rel).is_absolute() else Path(rel)
    # 允许直接用文件名
    candidate = TEMPLATES / f"{project_id}.yaml"
    if candidate.exists():
        return candidate
    raise KeyError(f"未知项目: {project_id}")


@lru_cache(maxsize=8)
def load_template(project_id: str) -> dict[str, Any]:
    data = _load_yaml(template_path(project_id))
    if data.get("project_id") and data["project_id"] != project_id:
        # 仍允许，但保留文件里的 id
        pass
    return data


def list_projects() -> list[str]:
    return list((settings().get("projects") or {}).keys())


def naming_regex(template: dict[str, Any]) -> re.Pattern[str]:
    raw = template["naming"]["pattern"]
    # YAML 里为了可读写成了带反斜杠的字符串；兼容已经编译过的。
    return re.compile(raw)


def type_prefix(template: dict[str, Any], asset_type: str) -> str:
    return template["naming"]["type_prefix"].get(asset_type, "prp")


def poly_budget_for(template: dict[str, Any], asset_type: str, lod: int) -> int | None:
    budgets = template.get("poly_budget") or {}
    row = budgets.get(asset_type) or budgets.get("default") or {}
    key = f"lod{lod}"
    return row.get(key)


def pot_policy(template: dict[str, Any], asset_type: str, *, is_3d_texture: bool = False) -> str:
    """返回 required / not_required。"""
    tex = template.get("texture") or {}
    policy = tex.get("power_of_two") or {}
    if is_3d_texture:
        return policy.get("3d_model_texture") or policy.get("texture") or "required"
    return policy.get(asset_type) or "not_required"


def check_severity(template: dict[str, Any], check_id: str) -> str:
    return (template.get("checks") or {}).get(check_id, "warn")


def slugify_name(name: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "", name.lower())
    return s or "asset"


def canonical_filename(template: dict[str, Any], asset_type: str, stem: str, ext: str, lod: int = 0, version: int = 1) -> str:
    prefix = type_prefix(template, asset_type)
    slug = slugify_name(stem)
    ext = ext.lstrip(".").lower()
    if ext == "jpeg":
        ext = "jpg"
    return f"{template['project_id'][0]}_{prefix}_{slug}_lod{lod}_v{version:03d}.{ext}".replace(
        f"{template['project_id'][0]}_",
        f"{type_prefix_project(template)}_",
        0,
    )


def type_prefix_project(template: dict[str, Any]) -> str:
    """项目前缀：模板 M 用 m，模板 R 用 r。从 example 或 project_id 约定读取。"""
    example = (template.get("naming") or {}).get("example", "")
    if example.startswith("m_"):
        return "m"
    if example.startswith("r_"):
        return "r"
    pid = template.get("project_id", "")
    return "m" if "stylized" in pid or pid.startswith("m") else "r"


def make_canonical(template: dict[str, Any], asset_type: str, stem: str, ext: str, lod: int = 0, version: int = 1) -> str:
    proj = type_prefix_project(template)
    prefix = type_prefix(template, asset_type)
    slug = slugify_name(stem)
    ext = ext.lstrip(".").lower()
    if ext == "jpeg":
        ext = "jpg"
    return f"{proj}_{prefix}_{slug}_lod{lod}_v{version:03d}.{ext}"


def infer_lod_from_name(name: str) -> int:
    m = re.search(r"lod([0-2])", name.lower())
    return int(m.group(1)) if m else 0


def clear_caches() -> None:
    settings.cache_clear()
    load_template.cache_clear()
