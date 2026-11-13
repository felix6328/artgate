from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
CONFIGS = REPO_ROOT / "configs"
TEMPLATES = CONFIGS / "templates"
SETTINGS_FILE = CONFIGS / "settings.yaml"
DATA = REPO_ROOT / "data"
RAW = DATA / "raw"
PREVIEWS = DATA / "previews"
BROKEN = DATA / "broken"
INDEX_DIR = DATA / "lancedb"
EMBED_CACHE = DATA / "embed_cache"
DB_PATH = DATA / "artgate.db"
COST_LOG = DATA / "cost.jsonl"
MANIFEST = DATA / "manifest.json"
LICENSES = DATA / "licenses.md"
CATALOG = DATA / "catalog.json"
EVAL = REPO_ROOT / "eval"
APP = REPO_ROOT / "app"
SCRIPTS = REPO_ROOT / "scripts"
NODE_MODULES = REPO_ROOT / "node_modules"


def ensure_dirs() -> None:
    for p in (DATA, RAW, PREVIEWS, BROKEN, INDEX_DIR, EMBED_CACHE, EVAL):
        p.mkdir(parents=True, exist_ok=True)
