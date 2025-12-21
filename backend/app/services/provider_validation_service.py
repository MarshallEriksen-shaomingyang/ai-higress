from __future__ import annotations

import time
from datetime import UTC, datetime
from typing import Any

from app.http_client import CurlCffiClient
from app.logging_config import logger
from app.schemas.provider_control import ProviderModelValidationResult, ProviderValidationResult


class ProviderValidationService:
    """提供商配置验证服务。

    该服务在用户提交共享提供商或创建私有提供商时，可以对 base_url + api_key
    做一次轻量级连通性检查，避免明显错误。
    """

    async def validate_provider_config(
        self,
        base_url: str,
        api_key: str,
        provider_type: str,
    ) -> ProviderValidationResult:
        """验证提供商配置是否可用。

        当前实现以 GET {base_url}/v1/models 或 {base_url}/models 为主，
        后续可以根据 provider_type 做更精细适配。
        """
        # 简单规范化，防止末尾多斜线
        base = base_url.rstrip("/")
        candidates = [f"{base}/v1/models", f"{base}/models"]

        headers = {"Authorization": f"Bearer {api_key}", "Accept": "application/json"}

        async with CurlCffiClient(
            timeout=10.0,
            impersonate="chrome120",
            trust_env=True,
        ) as client:
            last_error: str | None = None
            for url in candidates:
                try:
                    resp = await client.get(url, headers=headers)
                except Exception as exc:  # pragma: no cover - 网络异常兜底
                    last_error = str(exc)
                    logger.warning("Provider validation HTTP error for %s: %s", url, exc)
                    continue

                if resp.status_code != 200:
                    last_error = f"HTTP {resp.status_code}"
                    continue

                try:
                    data = resp.json()
                except ValueError:
                    last_error = "响应不是合法 JSON"
                    continue

                if not isinstance(data, dict) or "data" not in data:
                    last_error = "响应格式不符合预期（缺少 data 字段）"
                    continue

                # 解析模型元数据
                metadata = self._extract_provider_metadata(data)
                return ProviderValidationResult(is_valid=True, metadata=metadata)

        return ProviderValidationResult(
            is_valid=False,
            error_message=last_error or "无法验证提供商配置",
        )

    def _extract_provider_metadata(self, models_payload: dict[str, Any]) -> dict[str, Any]:
        """从 /models 响应中提取基础元数据."""
        raw_models = models_payload.get("data") or []
        if not isinstance(raw_models, list):
            return {"model_count": 0, "model_families": [], "sample_models": []}

        families: set[str] = set()
        total_context = 0
        ctx_count = 0

        for item in raw_models:
            if not isinstance(item, dict):
                continue
            model_id = str(item.get("id") or "")
            family = item.get("family") or self._guess_family_from_id(model_id)
            if family:
                families.add(family)
            context_len = item.get("context_length") or item.get("max_context_length")
            try:
                if context_len is not None:
                    total_context += int(context_len)
                    ctx_count += 1
            except (TypeError, ValueError):
                continue

        avg_ctx = total_context // ctx_count if ctx_count > 0 else 0

        return {
            "model_families": sorted(families),
            "model_count": len(raw_models),
            "avg_context_length": avg_ctx,
            "sample_models": raw_models[:5],
        }

    def _guess_family_from_id(self, model_id: str) -> str | None:
        """尝试从模型 ID 推断家族名称."""
        lowered = model_id.lower()
        if "gpt-4" in lowered or "gpt-3.5" in lowered:
            return "openai"
        if "claude" in lowered:
            return "anthropic"
        if "gemini" in lowered:
            return "google"
        return None

    async def validate_models_via_chat(
        self,
        base_url: str,
        api_key: str,
        model_ids: list[str],
        *,
        path: str = "/v1/chat/completions",
        sample_prompt: str = "ping",
        timeout: float = 5.0,
        sample_size: int = 1,
    ) -> list[ProviderModelValidationResult]:
        """
        通过一次极小的 Chat 调用验证静态模型是否可用。

        - 仅取前 sample_size 个模型，避免成本过高。
        - 使用极短 prompt + max_tokens=1，减少计费。
        - 无论成功与否都返回结果，方便管理员查看错误信息。
        """
        results: list[ProviderModelValidationResult] = []
        if not model_ids:
            return results

        target_models = model_ids[:sample_size]
        async with CurlCffiClient(
            timeout=timeout,
            impersonate="chrome120",
            trust_env=True,
        ) as client:
            for model_id in target_models:
                url = f"{base_url.rstrip('/')}/{path.lstrip('/')}"
                payload = {
                    "model": model_id,
                    "messages": [{"role": "user", "content": sample_prompt}],
                    "max_tokens": 1,
                    "stream": False,
                }
                headers = {
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                }
                latency_ms: int | None = None
                try:
                    start = time.perf_counter()
                    response = await client.post(url, json=payload, headers=headers)
                    latency_ms = int((time.perf_counter() - start) * 1000.0)
                    timestamp = datetime.now(UTC)
                    if response.status_code < 300:
                        results.append(
                            ProviderModelValidationResult(
                                model_id=model_id,
                                success=True,
                                latency_ms=latency_ms,
                                error_message=None,
                                timestamp=timestamp,
                            )
                        )
                    else:
                        results.append(
                            ProviderModelValidationResult(
                                model_id=model_id,
                                success=False,
                                latency_ms=latency_ms,
                                error_message=f"HTTP {response.status_code}",
                                timestamp=timestamp,
                            )
                        )
                except Exception as exc:  # pragma: no cover - 网络/超时异常
                    logger.warning("Model validation failed for %s: %s", model_id, exc)
                    timestamp = datetime.now(UTC)
                    results.append(
                        ProviderModelValidationResult(
                            model_id=model_id,
                            success=False,
                            latency_ms=latency_ms,
                            error_message=str(exc),
                            timestamp=timestamp,
                        )
                    )
        return results


__all__ = ["ProviderValidationService"]
