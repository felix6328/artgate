"""OpenCLIP 多语言模型：XLM-Roberta-Base + ViT-B/32，LAION-5B。

嵌入本地计算，按文件哈希缓存，重复入库不二次计算。API 费用为 0。
中文查询必须用这个模型，不要默认英文 CLIP。
"""
from __future__ import annotations

import json
import threading
import time
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image

from artgate.config import settings
from artgate.db import log_cost
from artgate.hashutil import bytes_sha256, file_sha256
from artgate.paths import EMBED_CACHE, ensure_dirs

_lock = threading.Lock()
_state: dict[str, Any] = {"model": None, "preprocess": None, "tokenizer": None, "device": "cpu", "dim": None}


def model_info() -> dict[str, Any]:
    cfg = settings()["embedder"]
    return {
        "model_name": cfg["model_name"],
        "pretrained": cfg["pretrained"],
        "device": cfg.get("device", "cpu"),
        "note": "OpenCLIP 官方多语言预训练：xlm-roberta-base-ViT-B-32 / laion5b_s13b_b90k",
    }


def _cache_path(key: str) -> Path:
    ensure_dirs()
    return EMBED_CACHE / f"{key}.npy"


def _ensure_hf_home():
    import os
    from artgate.paths import REPO_ROOT
    os.environ.setdefault("HF_HOME", str(REPO_ROOT / ".cache" / "huggingface"))


def load_model(force: bool = False):
    with _lock:
        if _state["model"] is not None and not force:
            return _state
        _ensure_hf_home()
        import torch
        import open_clip

        cfg = settings()["embedder"]
        device = cfg.get("device", "cpu")
        torch.set_num_threads(max(1, int(torch.get_num_threads() or 4)))
        # 限制线程，避免在 16GB 机器上抢光资源
        try:
            torch.set_num_threads(4)
        except Exception:
            pass
        t0 = time.perf_counter()
        model, _, preprocess = open_clip.create_model_and_transforms(
            cfg["model_name"],
            pretrained=cfg["pretrained"],
            device=device,
        )
        tokenizer = open_clip.get_tokenizer(cfg["model_name"])
        model.eval()
        # 试探维度
        with torch.no_grad():
            dummy = tokenizer(["hello"])
            if hasattr(dummy, "to"):
                dummy = dummy.to(device)
            text_feat = model.encode_text(dummy)
            dim = int(text_feat.shape[-1])
        _state.update({
            "model": model,
            "preprocess": preprocess,
            "tokenizer": tokenizer,
            "device": device,
            "dim": dim,
            "torch": torch,
        })
        ms = (time.perf_counter() - t0) * 1000
        log_cost("embed_load", duration_ms=ms, estimated_cny=0, ok=True, details=model_info())
        return _state


def embed_images(paths: list[Path], *, asset_ids: list[str] | None = None) -> np.ndarray:
    if not paths:
        return np.zeros((0, load_model()["dim"]), dtype=np.float32)
    st = load_model()
    torch = st["torch"]
    cfg = settings()["embedder"]
    batch_size = int(cfg.get("batch_size") or 4)
    out = [None] * len(paths)
    pending_idx = []
    pending_imgs = []
    for i, p in enumerate(paths):
        p = Path(p)
        key = None
        if p.exists():
            key = "img_" + file_sha256(p)
            cp = _cache_path(key)
            if cp.exists():
                out[i] = np.load(cp)
                continue
        pending_idx.append(i)
        pending_imgs.append((p, key))

    for start in range(0, len(pending_imgs), batch_size):
        chunk = pending_imgs[start : start + batch_size]
        idxs = pending_idx[start : start + batch_size]
        tensors = []
        valid = []
        t0 = time.perf_counter()
        for j, (p, key) in enumerate(chunk):
            try:
                im = Image.open(p).convert("RGB")
                tensors.append(st["preprocess"](im))
                valid.append(j)
            except Exception:
                # 读失败：用零向量，调用方应察觉
                dim = st["dim"]
                out[idxs[j]] = np.zeros((dim,), dtype=np.float32)
        if not tensors:
            continue
        batch = torch.stack(tensors).to(st["device"])
        with torch.no_grad():
            feat = st["model"].encode_image(batch)
            feat = feat / feat.norm(dim=-1, keepdim=True)
            arr = feat.cpu().numpy().astype(np.float32)
        ms = (time.perf_counter() - t0) * 1000
        log_cost(
            "embed_image",
            duration_ms=ms,
            estimated_cny=0,
            ok=True,
            details={"n": len(tensors), "batch_size": batch_size},
        )
        k = 0
        for j in valid:
            vec = arr[k]
            k += 1
            out[idxs[j]] = vec
            key = chunk[j][1]
            if key:
                np.save(_cache_path(key), vec)
    # fill any leftover Nones
    dim = st["dim"]
    result = np.stack([v if v is not None else np.zeros((dim,), dtype=np.float32) for v in out], axis=0)
    return result


def embed_texts(texts: list[str]) -> np.ndarray:
    st = load_model()
    torch = st["torch"]
    t0 = time.perf_counter()
    tok = st["tokenizer"](texts)
    if hasattr(tok, "to"):
        tok = tok.to(st["device"])
    with torch.no_grad():
        feat = st["model"].encode_text(tok)
        feat = feat / feat.norm(dim=-1, keepdim=True)
        arr = feat.cpu().numpy().astype(np.float32)
    ms = (time.perf_counter() - t0) * 1000
    log_cost(
        "embed_text",
        input_hash=bytes_sha256(("\n".join(texts)).encode("utf-8")),
        duration_ms=ms,
        estimated_cny=0,
        ok=True,
        details={"n": len(texts)},
    )
    return arr


def available() -> tuple[bool, str]:
    try:
        load_model()
        return True, "ok"
    except Exception as e:
        return False, f"{type(e).__name__}: {e}"
