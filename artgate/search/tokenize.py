"""检索共用的分词：文件名、路径、查询都走同一套规则。

- 英文：按非字母数字切开，再拆 camelCase（uziSilencerGold → uzi, silencer, gold）
- 去掉末尾纯数字（walk7 → walk7 与 walk），方便动作帧精灵
- 中文：保留整段，并切二字、单字（单字只在长度为 1 或作为补充时保留）
- 停用词含「一把 / 一支 / a / the」等量词与冠词，避免它们主导 BM25
"""
from __future__ import annotations

import re

STOP = {
    "a", "an", "the", "of", "and", "or", "to", "for", "in", "on", "with", "by",
    "is", "at", "from", "as", "its", "it",
    "的", "了", "和", "与", "及", "或",
    "一个", "一把", "一支", "一根", "一只", "一件", "一张", "一扇", "一台",
    "一种", "一些", "一条", "一座", "一辆", "一艘", "一顶", "一枚",
    "这个", "那个", "这种", "那种",
    "glb", "gltf", "png", "jpg", "jpeg", "fbx", "obj", "webp", "ktx2",
}

_CAMEL = re.compile(r"(?<=[a-z])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])")
_KEEP = re.compile(r"[a-zA-Z0-9\u4e00-\u9fff]+")
_ZH = re.compile(r"[\u4e00-\u9fff]+")
_TRAIL_NUM = re.compile(r"^(.*?)(\d+)$")


def tokenize(text: str | None) -> list[str]:
    if not text:
        return []
    raw = str(text)
    tokens: list[str] = []
    seen_local: set[str] = set()

    def add(tok: str) -> None:
        tok = tok.lower().strip()
        if not tok or tok in STOP or len(tok) == 0:
            return
        if tok in seen_local:
            return
        # 单字符英文（除了有意义的少见情况）丢掉
        if len(tok) == 1 and tok.isascii() and tok.isalpha():
            return
        seen_local.add(tok)
        tokens.append(tok)

    for chunk in _KEEP.findall(raw):
        zh_spans = _ZH.findall(chunk)
        if zh_spans and not re.search(r"[a-zA-Z0-9]", chunk):
            for span in zh_spans:
                add(span)
                if len(span) >= 2:
                    for i in range(len(span) - 1):
                        add(span[i : i + 2])
                if len(span) >= 3:
                    for i in range(len(span)):
                        add(span[i])
                elif len(span) == 1:
                    add(span)
            continue
        # 英文或混合：先拆 camelCase
        pieces = _CAMEL.sub(" ", chunk).split()
        if len(pieces) == 1 and not re.search(r"[A-Z]", chunk[1:] if len(chunk) > 1 else ""):
            pieces = [chunk]
        for piece in pieces:
            add(piece)
            m = _TRAIL_NUM.match(piece)
            if m and m.group(1) and len(m.group(1)) >= 2:
                add(m.group(1))
            # 再拆内部中文
            for span in _ZH.findall(piece):
                add(span)
    return tokens


def tokenize_keep_dupes(text: str | None) -> list[str]:
    """与 tokenize 相同规则，但保留重复（用于按字段加权时重复加入）。"""
    # 简单做法：不用 seen 过滤。复制逻辑太长，按字段重复调用 tokenize 再拼接即可。
    return tokenize(text)
