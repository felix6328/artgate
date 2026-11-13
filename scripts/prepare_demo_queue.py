#!/usr/bin/env python3
"""把若干损坏 / 合规样本送进人工队列，供 Demo 演示 TA 改判。不入检索库。"""
from __future__ import annotations
import sys
from pathlib import Path
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from artgate.ingest.importer import ingest_file
from artgate.paths import EVAL

def main():
    gold = yaml.safe_load((EVAL / "gold_precheck.yaml").read_text())
    # 选有演示价值的几条
    want = {
        "bad_name_final_final2",
        "npot_1000x800_texture",
        "overbudget_icosphere",
        "name_mismatch_shield_is_sword",
        "npot_ui_not_required",
        "compliant_sword",
        "style_drift_realistic_in_stylized",
        "invalid_gltf_missing_accessor",
    }
    n = 0
    for it in gold["items"]:
        if it["id"] not in want:
            continue
        path = ROOT / it["path"]
        if not path.exists():
            print("missing", path)
            continue
        # 名实不符用 mock，展示视觉 warn
        vlm = "mock" if it.get("visual_only") else "disabled"
        r = ingest_file(
            path,
            it["project_id"],
            asset_type=it.get("asset_type") or "prop",
            source="demo_queue",
            source_pack="broken",
            license_name="derived from CC0 / test fixture",
            canonical_name=it.get("canonical_name"),
            original_filename=path.name,
            copy=False,
            auto_status="pending",
            skip_vlm=(vlm == "disabled"),
            vlm_backend=vlm,
            uploader="demo",
        )
        print(it["id"], r["report"]["overall"], r["asset_id"])
        n += 1
    print("queued", n)

if __name__ == "__main__":
    main()
