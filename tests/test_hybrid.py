#!/usr/bin/env python3
"""不依赖 OpenCLIP 的 v2 检索单元测试。"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from artgate.search.tokenize import tokenize
from artgate.search.expand import expand, load_lexicon
from artgate.search.hybrid import classify_query, rrf_fuse
from artgate.search.bm25 import BM25Index, document_tokens


def test_tokenize_camel_and_kebab():
    toks = tokenize("uziSilencerGold.glb")
    assert "uzi" in toks and "silencer" in toks and "gold" in toks
    toks2 = tokenize("weapon-sword.glb")
    assert "weapon" in toks2 and "sword" in toks2
    toks3 = tokenize("character_femaleAdventurer_walk7.png")
    assert "female" in toks3 and "adventurer" in toks3 and "walk" in toks3


def test_expand_sword_not_knife():
    ex = expand("一把剑")
    assert "剑" in ex.matched_terms
    assert "sword" in ex.added_terms
    assert "blade" in ex.added_terms
    assert "knife" not in ex.added_terms
    assert "sword" in ex.bm25_tokens
    # 停用「一把」
    assert "一把" not in ex.bm25_tokens


def test_expand_shield_shapes():
    ex = expand("圆形盾牌")
    assert "shield" in ex.added_terms
    assert "round" in ex.added_terms or "circular" in ex.added_terms
    ex2 = expand("长方形盾牌")
    assert "shield" in ex2.added_terms
    assert "rectangle" in ex2.added_terms or "rectangular" in ex2.added_terms


def test_classify():
    assert classify_query("一把剑") == "descriptive"
    assert classify_query("a sword") == "filename_like"
    assert classify_query("weapon-sword.glb") == "filename_like"
    assert classify_query("a worn wooden round shield on the table") == "descriptive"


def test_rrf_and_bm25_toy():
    docs = [
        {"id": "a", "original_filename": "weapon-sword.glb", "source_pack": "mini-dungeon",
         "asset_type": "weapon", "tags": ["sword", "weapon"], "description": "a sword",
         "canonical_name": "m_wpn_sword_lod0_v001.glb", "original_path": "", "project_id": "m",
         "format": "glb", "triangles": 80, "status": "approved", "source": "kenney"},
        {"id": "b", "original_filename": "knife_sharp.glb", "source_pack": "weapon",
         "asset_type": "weapon", "tags": ["knife", "weapon"], "description": "a knife",
         "canonical_name": "m_wpn_knife_lod0_v001.glb", "original_path": "", "project_id": "m",
         "format": "glb", "triangles": 40, "status": "approved", "source": "kenney"},
        {"id": "c", "original_filename": "shield-round.glb", "source_pack": "mini-dungeon",
         "asset_type": "weapon", "tags": ["shield", "round"], "description": "round shield",
         "canonical_name": "m_wpn_shieldround_lod0_v001.glb", "original_path": "", "project_id": "m",
         "format": "glb", "triangles": 90, "status": "approved", "source": "kenney"},
    ]
    idx = BM25Index()
    idx.build(docs)
    ex = expand("一把剑")
    hits = idx.search(ex.bm25_tokens, project_id="m", top_k=5, cross_project=False)
    ids = [h["id"] for h in hits]
    assert ids[0] == "a", ids
    assert "b" not in ids[:1]

    # RRF：语义把刀排第一、剑排第三；词法把剑排第一 → 融合后剑应上升
    sem = [{"id": "b", "score": 0.4}, {"id": "c", "score": 0.35}, {"id": "a", "score": 0.3}]
    fused = rrf_fuse({"semantic": sem, "bm25": hits}, weights={"semantic": 1, "bm25": 1}, k=60, top_k=3)
    assert fused[0]["id"] == "a", [(x["id"], x["score"], x.get("component_ranks")) for x in fused]


def test_lexicon_loads():
    lex = load_lexicon()
    assert "剑" in lex and "sword" in lex["剑"]
    assert "knife" not in lex["剑"]


if __name__ == "__main__":
    tests = [
        test_tokenize_camel_and_kebab,
        test_expand_sword_not_knife,
        test_expand_shield_shapes,
        test_classify,
        test_rrf_and_bm25_toy,
        test_lexicon_loads,
    ]
    for t in tests:
        t()
        print("ok", t.__name__)
    print("all passed", len(tests))
