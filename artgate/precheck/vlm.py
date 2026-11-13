"""可插拔的 VLM 视觉建议层。

只做规则写不死的事：文件名/标签与画面是否一致、是否偏离风格参考板。
输出必须是结构化 JSON：issue_code、证据、置信度、建议级别。
禁止自由散文，禁止给出面数或像素数值。

后端：
- disabled：不调用，视觉项标 not_run / 未完成（默认，无 API key）
- mock：仅对夹具清单里的样本返回预定结果，用于演示流水线，不是评测
- openai_compat：在提供 ARTGATE_VLM_API_KEY 或 OPENAI_API_KEY 时调用
失败 / 超时 / 低置信 / 解析失败：降级为仅规则结果，不编评语。
"""
from __future__ import annotations

import json
import os
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Protocol

from artgate.config import settings
from artgate.db import log_cost
from artgate.hashutil import file_sha256


@dataclass
class VLMIssue:
    issue_code: str  # name_content_mismatch | style_drift | uncertain | none
    confidence: float
    suggested_severity: str  # warn | block | info
    evidence: str
    verdict: str  # mismatch | match | drift | consistent | uncertain | skipped


@dataclass
class VLMResult:
    ran: bool
    backend: str
    status: str  # ok | skipped | disabled | timeout | parse_failed | low_confidence | error
    issues: list[VLMIssue] = field(default_factory=list)
    raw: Any = None
    message: str = ""
    duration_ms: float = 0.0
    cached: bool = False

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        return d


# 夹具：mock 后端只对这些「已知名实不符 / 风格漂移」样本给出警告。
# 键是原始文件名或 canonical 名的子串，由 create_broken_assets 与此保持一致。
MOCK_MISMATCH_STEMS = {
    "name_mismatch_shield_is_sword",
    "m_wpn_shieldround_lod0_v001",  # 内容实际是剑
}
MOCK_STYLE_DRIFT_STEMS = {
    "style_drift_realistic_in_stylized",
    "camerafancy",
    "style_drift",
}


class VLMBackend(Protocol):
    name: str

    def review(
        self,
        image_path: Path | None,
        filename: str,
        tags: list[str],
        style_refs: list[Path],
        schema: dict[str, Any],
        *,
        asset_id: str | None = None,
    ) -> VLMResult:
        ...


class DisabledVLM:
    name = "disabled"

    def review(self, image_path, filename, tags, style_refs, schema, *, asset_id=None) -> VLMResult:
        return VLMResult(
            ran=False,
            backend=self.name,
            status="disabled",
            message="未配置 VLM（无 API key 或 backend=disabled）。预检只保留规则层，视觉项标为未完成。",
        )


class MockVLM:
    name = "mock"

    def review(self, image_path, filename, tags, style_refs, schema, *, asset_id=None) -> VLMResult:
        t0 = time.perf_counter()
        stem = Path(filename).stem.lower()
        blob = " ".join([stem, *(tags or []), asset_id or ""]).lower()
        issues: list[VLMIssue] = []
        for key in MOCK_MISMATCH_STEMS:
            if key.lower() in blob:
                issues.append(VLMIssue(
                    issue_code="name_content_mismatch",
                    confidence=0.92,
                    suggested_severity="warn",
                    evidence="mock：夹具标记为「文件名是盾、内容是剑」。这不是真实 VLM 判断。",
                    verdict="mismatch",
                ))
        for key in MOCK_STYLE_DRIFT_STEMS:
            if key.lower() in blob:
                issues.append(VLMIssue(
                    issue_code="style_drift",
                    confidence=0.88,
                    suggested_severity="warn",
                    evidence="mock：夹具标记为写实资产进入风格化项目。这不是真实 VLM 判断。",
                    verdict="drift",
                ))
        if not issues:
            issues.append(VLMIssue(
                issue_code="none",
                confidence=0.7,
                suggested_severity="info",
                evidence="mock：不在夹具清单内，返回无视觉问题（不能当作真实评测）。",
                verdict="match",
            ))
        ms = (time.perf_counter() - t0) * 1000
        log_cost("vlm_mock", asset_id=asset_id, duration_ms=ms, estimated_cny=0, ok=True, details={"filename": filename})
        return VLMResult(
            ran=True,
            backend=self.name,
            status="ok",
            issues=issues,
            message="mock 后端仅用于演示流水线，视觉层精确率不得写入简历。",
            duration_ms=ms,
        )


class OpenAICompatVLM:
    name = "openai_compat"

    def __init__(self, cfg: dict[str, Any]):
        self.cfg = cfg
        self.api_key = os.environ.get("ARTGATE_VLM_API_KEY") or os.environ.get("OPENAI_API_KEY") or ""
        self.base_url = (cfg.get("base_url") or os.environ.get("ARTGATE_VLM_BASE_URL") or "https://api.openai.com/v1").rstrip("/")
        self.model = cfg.get("model") or os.environ.get("ARTGATE_VLM_MODEL") or "gpt-4o-mini"
        self.timeout = float(cfg.get("timeout_sec") or 30)
        self.threshold = float(cfg.get("confidence_threshold") or 0.6)
        self.est_cny = float(cfg.get("estimated_cny_per_call") or 0)

    def review(self, image_path, filename, tags, style_refs, schema, *, asset_id=None) -> VLMResult:
        if not self.api_key:
            return VLMResult(
                ran=False,
                backend=self.name,
                status="disabled",
                message="openai_compat 已选但未提供 ARTGATE_VLM_API_KEY / OPENAI_API_KEY，降级为不调用。",
            )
        if image_path is None or not Path(image_path).exists():
            return VLMResult(
                ran=False,
                backend=self.name,
                status="error",
                message="没有可用预览图，视觉项未完成。",
            )
        import base64
        from io import BytesIO

        import httpx
        from PIL import Image

        t0 = time.perf_counter()
        try:
            max_side = int(self.cfg.get("thumbnail_max_side") or 512)
            im = Image.open(image_path).convert("RGB")
            im.thumbnail((max_side, max_side))
            buf = BytesIO()
            im.save(buf, format="JPEG", quality=85)
            b64 = base64.b64encode(buf.getvalue()).decode("ascii")
            prompt = (
                "你是游戏美术入库预检的视觉检查器。只判断两件事："
                "1) 文件名/标签与画面内容是否明显不符；"
                "2) 相对项目风格参考，是否明显风格偏离。"
                "禁止估计或输出面数、像素、文件格式等数值。"
                "必须只输出 JSON，字段：issues: [{issue_code, confidence, suggested_severity, evidence, verdict}]。"
                "issue_code 只能是 name_content_mismatch、style_drift、none。"
                f"文件名: {filename}; 标签: {tags}; 项目风格: {schema.get('style')}。"
            )
            url = f"{self.base_url}/chat/completions"
            payload = {
                "model": self.model,
                "temperature": 0,
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}},
                        ],
                    }
                ],
            }
            headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
            with httpx.Client(timeout=self.timeout) as client:
                resp = client.post(url, json=payload, headers=headers)
            ms = (time.perf_counter() - t0) * 1000
            if resp.status_code >= 400:
                log_cost("vlm", asset_id=asset_id, duration_ms=ms, estimated_cny=0, ok=False, details={"status": resp.status_code})
                return VLMResult(ran=False, backend=self.name, status="error", message=f"VLM HTTP {resp.status_code}", duration_ms=ms)
            body = resp.json()
            text = body["choices"][0]["message"]["content"]
            parsed = _parse_json_maybe(text)
            if parsed is None:
                log_cost("vlm", asset_id=asset_id, duration_ms=ms, estimated_cny=self.est_cny, ok=False)
                return VLMResult(ran=False, backend=self.name, status="parse_failed", message="VLM 输出无法解析为 JSON，视觉项未完成。", raw=text, duration_ms=ms)
            issues = []
            for it in parsed.get("issues") or []:
                conf = float(it.get("confidence") or 0)
                issues.append(VLMIssue(
                    issue_code=it.get("issue_code") or "uncertain",
                    confidence=conf,
                    suggested_severity=it.get("suggested_severity") or "warn",
                    evidence=str(it.get("evidence") or "")[:500],
                    verdict=it.get("verdict") or "uncertain",
                ))
            # 低置信 → uncertain，不给通过/退回建议
            status = "ok"
            for iss in issues:
                if iss.confidence < self.threshold and iss.issue_code != "none":
                    iss.verdict = "uncertain"
                    iss.issue_code = "uncertain"
                    iss.evidence = (iss.evidence + " （低于置信阈值，不作为通过建议）").strip()
                    status = "low_confidence"
            log_cost(
                "vlm",
                asset_id=asset_id,
                input_hash=file_sha256(Path(image_path)),
                duration_ms=ms,
                estimated_cny=self.est_cny,
                ok=True,
                details={"model": self.model, "note": "费用为假设单价，不是账单"},
            )
            return VLMResult(ran=True, backend=self.name, status=status, issues=issues, raw=parsed, duration_ms=ms)
        except httpx.TimeoutException:
            ms = (time.perf_counter() - t0) * 1000
            log_cost("vlm", asset_id=asset_id, duration_ms=ms, ok=False, details={"timeout": True})
            return VLMResult(ran=False, backend=self.name, status="timeout", message="VLM 超时，视觉项未完成，仅保留规则层。", duration_ms=ms)
        except Exception as e:
            ms = (time.perf_counter() - t0) * 1000
            log_cost("vlm", asset_id=asset_id, duration_ms=ms, ok=False, details={"error": str(e)})
            return VLMResult(ran=False, backend=self.name, status="error", message=f"VLM 失败: {type(e).__name__}: {e}，仅保留规则层。", duration_ms=ms)


def _parse_json_maybe(text: str) -> dict | None:
    text = text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.startswith("json"):
            text = text[4:]
        text = text.strip()
    try:
        data = json.loads(text)
        return data if isinstance(data, dict) else {"issues": data}
    except json.JSONDecodeError:
        a, b = text.find("{"), text.rfind("}")
        if a >= 0 and b > a:
            try:
                return json.loads(text[a : b + 1])
            except json.JSONDecodeError:
                return None
        return None


def get_backend(override: str | None = None) -> VLMBackend:
    cfg = (settings().get("vlm") or {})
    name = (override or cfg.get("backend") or "disabled").lower()
    if name == "mock":
        return MockVLM()
    if name == "openai_compat":
        return OpenAICompatVLM(cfg)
    return DisabledVLM()
