"""手写同义词表的查询扩展。默认只扩展给 BM25 一路。"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from artgate.paths import REPO_ROOT
from artgate.search.tokenize import STOP, tokenize

DEFAULT_PATH = REPO_ROOT / "configs" / "synonyms_game_art.yaml"


@dataclass
class Expansion:
    original: str
    original_tokens: list[str]
    matched_terms: list[str] = field(default_factory=list)
    added_terms: list[str] = field(default_factory=list)
    bm25_tokens: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "original": self.original,
            "original_tokens": self.original_tokens,
            "matched_terms": self.matched_terms,
            "added_terms": self.added_terms,
            "bm25_tokens": self.bm25_tokens,
        }


@lru_cache(maxsize=4)
def load_lexicon(path: str | None = None) -> dict[str, list[str]]:
    p = Path(path) if path else DEFAULT_PATH
    data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    terms = data.get("terms") or {}
    out: dict[str, list[str]] = {}
    for k, v in terms.items():
        key = str(k).strip()
        if not key:
            continue
        if isinstance(v, dict):
            vals = v.get("en") or v.get("aliases") or []
        elif isinstance(v, list):
            vals = v
        else:
            vals = [v]
        aliases = []
        for a in vals:
            s = str(a).strip().lower()
            if s and s not in aliases and s != key.lower():
                aliases.append(s)
        if aliases:
            out[key] = aliases
    return out


def expand(query: str, *, lexicon: dict[str, list[str]] | None = None) -> Expansion:
    q = query or ""
    lex = lexicon if lexicon is not None else load_lexicon()
    orig_tokens = tokenize(q)
    # 按长度从长到短，避免「盾」抢在「盾牌」前面
    keys = sorted(lex.keys(), key=lambda s: (-len(s), s))
    q_lower = q.lower()
    matched: list[str] = []
    added: list[str] = []
    occupied = [False] * len(q)

    def can_take(start: int, end: int) -> bool:
        if start < 0 or end > len(q) or start >= end:
            return False
        return not any(occupied[start:end])

    for term in keys:
        is_ascii = all(ord(c) < 128 for c in term)
        if is_ascii:
            pattern = re.compile(r"(?<![a-z0-9])" + re.escape(term.lower()) + r"(?![a-z0-9])")
            for m in pattern.finditer(q_lower):
                if can_take(m.start(), m.end()):
                    for i in range(m.start(), m.end()):
                        occupied[i] = True
                    if term not in matched:
                        matched.append(term)
                    for a in lex[term]:
                        if a not in added and a not in orig_tokens:
                            added.append(a)
        else:
            start = 0
            while True:
                idx = q.find(term, start)
                if idx < 0:
                    break
                if can_take(idx, idx + len(term)):
                    for i in range(idx, idx + len(term)):
                        occupied[i] = True
                    if term not in matched:
                        matched.append(term)
                    for a in lex[term]:
                        if a not in added and a not in orig_tokens:
                            added.append(a)
                start = idx + 1

    # BM25 查询词：原词（已去停用）+ 扩展英文。扩展词只加一次，不额外加权。
    bm25_tokens = list(orig_tokens)
    for a in added:
        for t in tokenize(a) or [a]:
            if t not in STOP and t not in bm25_tokens:
                bm25_tokens.append(t)
    return Expansion(
        original=q,
        original_tokens=orig_tokens,
        matched_terms=matched,
        added_terms=added,
        bm25_tokens=bm25_tokens,
    )
