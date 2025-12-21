"""
Provider 选择器（v2）

目标：把 chat 路由中的“解析/发现/选路”逻辑收敛到一个可复用模块，避免在 route 层堆积：
- Resolve：加载静态 LogicalModel（Redis）或动态构建（/models 缓存）
- Filter：应用用户可访问 provider ∩ API Key 白名单（上层传入 effective_provider_ids）
- Decide：加载指标/动态权重/粘性会话，调用调度器得到候选顺序（selected first）
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any
from uuid import UUID

import httpx
from fastapi import HTTPException, status
from sqlalchemy import select

try:
    from redis.asyncio import Redis
except ModuleNotFoundError:  # pragma: no cover
    Redis = object  # type: ignore

from sqlalchemy.orm import Session as DbSession

from app.api.v1.chat.routing_state import RoutingStateService
from app.logging_config import logger
from app.models import Provider, ProviderModel
from app.routing.mapper import select_candidate_upstreams
from app.routing.scheduler import CandidateScore, choose_upstream
from app.routing.session_manager import get_session
from app.schemas import (
    LogicalModel,
    ModelCapability,
    PhysicalModel,
    RoutingMetrics,
)
from app.schemas import (
    Session as RoutingSession,
)
from app.services.bandit_routing_weight_service import build_bandit_routing_weights
from app.services.chat_routing_service import _build_dynamic_logical_model_for_group, _build_ordered_candidates
from app.services.credit_service import estimate_request_cost_credits
from app.settings import settings
from app.storage.redis_service import get_logical_model


def _status_worse(a: Any, b: Any) -> bool:
    order = {"healthy": 0, "degraded": 1, "down": 2}
    return order.get(getattr(b, "value", str(b)), 0) > order.get(getattr(a, "value", str(a)), 0)


def _infer_required_capabilities_from_request_payload(
    request_payload: dict[str, Any] | None,
) -> set[ModelCapability]:
    """
    基于请求 payload（通常是 OpenAI chat.completions 风格）推断本次请求所需的 capability。

    目标：用于 eval / auto 选模阶段的“可行候选池过滤”，不追求 100% 完整覆盖，
    但要对 tools / vision / audio 等关键能力做保守约束。
    """
    if not isinstance(request_payload, dict):
        return set()

    required: set[ModelCapability] = set()

    tools = request_payload.get("tools")
    functions = request_payload.get("functions")
    tool_choice = request_payload.get("tool_choice")
    function_call = request_payload.get("function_call")
    if (
        (isinstance(tools, list) and tools)
        or (isinstance(functions, list) and functions)
        or (tool_choice not in (None, "none"))
        or (function_call not in (None, "none"))
    ):
        required.add(ModelCapability.FUNCTION_CALLING)

    messages = request_payload.get("messages")
    if isinstance(messages, list):
        for msg in messages:
            if not isinstance(msg, dict):
                continue
            content = msg.get("content")
            if isinstance(content, list):
                for part in content:
                    if not isinstance(part, dict):
                        continue
                    part_type = part.get("type")
                    if part_type in ("image_url", "input_image"):
                        required.add(ModelCapability.VISION)
                    if part_type in ("input_audio", "audio"):
                        required.add(ModelCapability.AUDIO)

    if isinstance(request_payload.get("audio"), dict):
        required.add(ModelCapability.AUDIO)

    return required


def _extract_token_hint(request_payload: dict[str, Any] | None) -> tuple[str, int] | None:
    if not isinstance(request_payload, dict):
        return None
    for key in ("max_tokens", "max_tokens_to_sample", "max_output_tokens"):
        value = request_payload.get(key)
        if isinstance(value, int) and value > 0:
            return key, int(value)
    return None


@dataclass(frozen=True)
class ProviderSelectionResult:
    logical_model: LogicalModel
    ordered_candidates: list[CandidateScore]
    scored_candidates: list[CandidateScore]
    base_weights: dict[str, float]


class ProviderSelector:
    """v2 Provider 选择器：负责 Resolve + Decide，返回有序候选列表。"""

    def __init__(
        self,
        *,
        client: httpx.AsyncClient,
        redis: Redis,
        db: DbSession,
        routing_state: RoutingStateService | None = None,
    ):
        self.client = client
        self.redis = redis
        self.db = db
        self.routing_state = routing_state or RoutingStateService(redis=redis)

    def _is_any_model_disabled(
        self,
        *,
        model_ids: list[str],
        provider_ids: set[str],
    ) -> bool:
        if not model_ids or not provider_ids:
            return False
        try:
            rows = (
                self.db.execute(
                    select(ProviderModel.model_id)
                    .join(Provider, ProviderModel.provider_id == Provider.id)
                    .where(Provider.provider_id.in_(list(provider_ids)))
                    .where(ProviderModel.model_id.in_(model_ids))
                    .where(ProviderModel.disabled.is_(True))
                    .limit(1)
                )
                .scalars()
                .all()
            )
            return bool(rows)
        except Exception:
            logger.exception(
                "provider_selector: failed to check model disabled state for model_ids=%s providers=%s",
                model_ids,
                sorted(provider_ids),
            )
            return False

    def _load_disabled_pairs(
        self,
        *,
        provider_ids: set[str],
        model_ids: set[str],
    ) -> set[tuple[str, str]]:
        if not provider_ids or not model_ids:
            return set()
        try:
            rows = self.db.execute(
                select(Provider.provider_id, ProviderModel.model_id)
                .select_from(ProviderModel)
                .join(Provider, ProviderModel.provider_id == Provider.id)
                .where(Provider.provider_id.in_(list(provider_ids)))
                .where(ProviderModel.model_id.in_(list(model_ids)))
                .where(ProviderModel.disabled.is_(True))
            ).all()
        except Exception:
            logger.exception(
                "provider_selector: failed to load disabled model pairs for providers=%s",
                sorted(provider_ids),
            )
            return set()
        disabled: set[tuple[str, str]] = set()
        for provider_id, model_id in rows:
            if isinstance(provider_id, str) and isinstance(model_id, str):
                disabled.add((provider_id, model_id))
        return disabled

    async def check_candidate_availability(
        self,
        *,
        candidate_logical_models: list[str],
        effective_provider_ids: set[str],
        api_style: str = "openai",
        user_id: UUID | None = None,
        is_superuser: bool = False,
        required_capabilities: set[ModelCapability] | None = None,
        request_payload: dict[str, Any] | None = None,
        budget_credits: int | None = None,
    ) -> list[str]:
        """
        Check which of the candidate logical models are currently available/feasible.
        
        A model is feasible if:
        1. It resolves to a valid LogicalModel (static or dynamic).
        2. It is enabled.
        3. It has at least one valid upstream (PhysicalModel) within effective_provider_ids.
        4. It is not disabled by provider/model pair.
        5. It is not fully down (health check).
        6. It has at least one upstream not in failure cooldown (routing_state).
        """
        available: list[str] = []
        derived_required_capabilities = required_capabilities
        if derived_required_capabilities is None and request_payload is not None:
            derived_required_capabilities = _infer_required_capabilities_from_request_payload(
                request_payload
            )

        cache_ttl = int(getattr(settings, "candidate_availability_cache_ttl_seconds", 0) or 0)
        cache_key: str | None = None
        if cache_ttl > 0 and self.redis is not object:
            token_hint = _extract_token_hint(request_payload)
            payload = {
                "v": 1,
                "candidate_logical_models": candidate_logical_models,
                "effective_provider_ids": sorted(effective_provider_ids),
                "api_style": api_style,
                "user_id": str(user_id) if user_id else None,
                "is_superuser": bool(is_superuser),
                "required_capabilities": sorted(
                    [c.value for c in (derived_required_capabilities or set())]
                ),
                "budget_credits": int(budget_credits) if budget_credits is not None else None,
                "token_hint": list(token_hint) if token_hint else None,
            }
            raw = json.dumps(payload, sort_keys=True, separators=(",", ":"))
            digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]
            cache_key = f"provider_selector:candidate_availability:{digest}"

            try:
                cached = await self.redis.get(cache_key)
            except Exception:
                cached = None
            if cached:
                try:
                    decoded = cached.decode("utf-8") if isinstance(cached, (bytes, bytearray)) else str(cached)
                    parsed = json.loads(decoded)
                except Exception:
                    parsed = None
                if isinstance(parsed, list) and all(isinstance(x, str) for x in parsed):
                    return list(parsed)
        # Pre-load disabled pairs for all relevant providers to avoid repetitive DB queries?
        # Optimization: We do it per model for now as the list is small.

        for model_id in candidate_logical_models:
            try:
                # 1) Resolve
                logical_model = await self._resolve_logical_model(
                    requested_model=model_id,
                    lookup_model_id=model_id,
                    api_style=api_style,
                    allowed_provider_ids=effective_provider_ids,
                    user_id=user_id,
                    is_superuser=is_superuser,
                )

                if not logical_model.enabled:
                    continue

                # 1.5) Capability constraints (logical-level)
                if derived_required_capabilities:
                    caps = set(logical_model.capabilities or [])
                    if not derived_required_capabilities.issubset(caps):
                        continue

                # 2) Candidates
                candidates: list[PhysicalModel] = select_candidate_upstreams(
                    logical_model,
                    preferred_region=None,
                    exclude_providers=[],
                )
                candidates = [c for c in candidates if c.provider_id in effective_provider_ids]
                candidates = [c for c in candidates if c.max_qps is None or int(c.max_qps) > 0]

                if not candidates:
                    continue

                # 3) API Style / Non-responses check
                if api_style in ("openai", "claude"):
                    non_responses = [
                        c for c in candidates if getattr(c, "api_style", "openai") != "responses"
                    ]
                    if not non_responses:
                        continue
                    candidates = non_responses

                # 4) Disabled pairs
                disabled_pairs = self._load_disabled_pairs(
                    provider_ids={c.provider_id for c in candidates},
                    model_ids={c.model_id for c in candidates},
                )
                if disabled_pairs:
                    candidates = [
                        c for c in candidates if (c.provider_id, c.model_id) not in disabled_pairs
                    ]

                if not candidates:
                    continue

                # 4.5) Failure cooldown / routing_state penalties
                if self.redis is not object:
                    skipped_providers: set[str] = set()
                    provider_ids = {c.provider_id for c in candidates}
                    for pid in provider_ids:
                        status_obj = await self.routing_state.get_failure_cooldown_status(pid)
                        if status_obj.should_skip:
                            skipped_providers.add(pid)
                    if skipped_providers:
                        candidates = [c for c in candidates if c.provider_id not in skipped_providers]

                if not candidates:
                    continue

                # 5) Health check
                healthy_or_unknown_providers: set[str] | None = None
                if settings.enable_provider_health_check and self.redis is not object:
                    down_providers: set[str] = set()
                    degraded_providers: set[str] = set()
                    healthy_or_unknown_providers = set()
                    for cand in candidates:
                        health = await self.routing_state.get_cached_health_status(cand.provider_id)
                        if health is None:
                            healthy_or_unknown_providers.add(cand.provider_id)
                            continue
                        status_value = getattr(getattr(health, "status", None), "value", None)
                        if status_value == "down":
                            down_providers.add(cand.provider_id)
                        elif status_value == "degraded":
                            degraded_providers.add(cand.provider_id)
                        else:
                            healthy_or_unknown_providers.add(cand.provider_id)

                    if down_providers:
                        candidates = [c for c in candidates if c.provider_id not in down_providers]

                    if candidates:
                        remaining_providers = {c.provider_id for c in candidates}
                        if not (remaining_providers & healthy_or_unknown_providers):
                            # 候选上游均处于 degraded（或未知状态被上面视为 healthy），则视为不可行候选。
                            # 对 eval/auto 选模更偏保守，避免把仅降级可用的模型纳入候选池。
                            if remaining_providers & degraded_providers:
                                candidates = []

                # 6) Budget feasibility (per-eval credits)
                if budget_credits is not None:
                    if not isinstance(request_payload, dict):
                        continue

                    budget_candidates = candidates
                    if healthy_or_unknown_providers is not None:
                        budget_candidates = [
                            c for c in budget_candidates if c.provider_id in healthy_or_unknown_providers
                        ]

                    feasible = False
                    for cand in budget_candidates:
                        cost = estimate_request_cost_credits(
                            self.db,
                            logical_model_name=logical_model.logical_id,
                            provider_id=cand.provider_id,
                            provider_model_id=cand.model_id,
                            request_payload=request_payload,
                        )
                        if cost is not None and cost <= int(budget_credits):
                            feasible = True
                            break
                    if not feasible:
                        continue

                if candidates:
                    available.append(model_id)

            except Exception:
                # Any failure in resolution or check means this model is not available.
                continue

        if cache_key and cache_ttl > 0 and self.redis is not object:
            try:
                await self.redis.setex(cache_key, cache_ttl, json.dumps(available))
            except Exception:
                pass
        return available

    async def select(
        self,
        *,
        requested_model: Any,
        lookup_model_id: str,
        api_style: str,
        effective_provider_ids: set[str],
        session_id: str | None = None,
        user_id: UUID | None = None,
        is_superuser: bool = False,
        bandit_project_id: UUID | None = None,
        bandit_assistant_id: UUID | None = None,
        bandit_user_text: str | None = None,
        bandit_request_payload: dict[str, Any] | None = None,
        bandit_context_features: dict[str, str] | None = None,
    ) -> ProviderSelectionResult:
        logical_model = await self._resolve_logical_model(
            requested_model=requested_model,
            lookup_model_id=lookup_model_id,
            api_style=api_style,
            allowed_provider_ids=effective_provider_ids,
            user_id=user_id,
            is_superuser=is_superuser,
        )

        if not logical_model.enabled:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Logical model '{logical_model.logical_id}' is disabled",
            )

        candidates: list[PhysicalModel] = select_candidate_upstreams(
            logical_model,
            preferred_region=None,
            exclude_providers=[],
        )
        candidates = [c for c in candidates if c.provider_id in effective_provider_ids]

        if not candidates:
            requested_model_str = (
                str(requested_model) if isinstance(requested_model, str) else None
            )
            model_ids_to_check: list[str] = [lookup_model_id]
            if requested_model_str and requested_model_str not in model_ids_to_check:
                model_ids_to_check.append(requested_model_str)
            if self._is_any_model_disabled(
                model_ids=model_ids_to_check, provider_ids=effective_provider_ids
            ):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail={"message": "该模型已被禁用"},
                )

        # 与 endpoint 选择逻辑保持一致：openai/claude 请求不应路由到 responses-only 上游。
        # 若所有候选都只能走 responses，则提示调用方切换到 /responses 入口。
        if api_style in ("openai", "claude"):
            non_responses = [
                c
                for c in candidates
                if getattr(c, "api_style", "openai") != "responses"
            ]
            if non_responses:
                candidates = non_responses
            else:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail={
                        "message": "该模型仅支持 Responses API，请使用 /responses 入口调用",
                        "requested_api_style": api_style,
                        "available_upstream_styles": ["responses"],
                    },
                )

        # Provider owner 的“模型禁用”过滤：禁用的 provider+model 不参与路由。
        disabled_pairs = self._load_disabled_pairs(
            provider_ids={c.provider_id for c in candidates},
            model_ids={c.model_id for c in candidates},
        )
        if disabled_pairs:
            candidates = [
                c for c in candidates if (c.provider_id, c.model_id) not in disabled_pairs
            ]

        if not candidates:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"message": "该模型已被禁用"},
            )

        # Optional: drop obvious down providers based on cached health.
        health_by_provider: dict[str, Any] = {}
        if settings.enable_provider_health_check and self.redis is not object:
            down_providers: set[str] = set()
            for cand in candidates:
                health = await self.routing_state.get_cached_health_status(cand.provider_id)
                if health is None:
                    continue
                health_by_provider[cand.provider_id] = health
                if health.status.value == "down":
                    down_providers.add(cand.provider_id)
            if down_providers:
                filtered = [c for c in candidates if c.provider_id not in down_providers]
                if filtered:
                    logger.info(
                        "provider_selector: filtered down providers by cached health: %s",
                        sorted(down_providers),
                    )
                    candidates = filtered

        base_weights: dict[str, float] = {c.provider_id: c.base_weight for c in candidates}

        session_obj: RoutingSession | None = None
        if session_id:
            session_obj = await get_session(self.redis, session_id)

        metrics_by_provider = await self.routing_state.load_metrics_for_candidates(
            logical_model.logical_id, candidates
        )

        # Overlay cached health onto metrics so the scheduler can penalize degraded providers.
        if settings.enable_provider_health_check and health_by_provider:
            active_provider_ids = {c.provider_id for c in candidates}
            for pid, health in health_by_provider.items():
                if pid not in active_provider_ids:
                    continue
                existing = metrics_by_provider.get(pid)
                if existing is None:
                    latency_ms = float(getattr(health, "response_time_ms", None) or 2000.0)
                    metrics_by_provider[pid] = RoutingMetrics(
                        logical_model=logical_model.logical_id,
                        provider_id=pid,
                        latency_p95_ms=max(1.0, latency_ms),
                        latency_p99_ms=max(1.0, latency_ms * 1.25),
                        error_rate=0.0,
                        success_qps_1m=0.0,
                        total_requests_1m=0,
                        last_updated=float(getattr(health, "timestamp", 0.0) or 0.0),
                        status=health.status,
                    )
                else:
                    if _status_worse(existing.status, health.status):
                        metrics_by_provider[pid] = existing.model_copy(update={"status": health.status})

        dynamic_weights = await self.routing_state.load_dynamic_weights(
            logical_model.logical_id, candidates
        )
        effective_dynamic_weights = dynamic_weights
        if (
            settings.enable_bandit_routing_weight
            and bandit_project_id is not None
            and bandit_assistant_id is not None
            and isinstance(bandit_user_text, str)
            and bandit_user_text.strip()
        ):
            try:
                policy_result = build_bandit_routing_weights(
                    self.db,
                    project_id=bandit_project_id,
                    assistant_id=bandit_assistant_id,
                    logical_model_id=logical_model.logical_id,
                    upstreams=candidates,
                    user_text=bandit_user_text,
                    request_payload=bandit_request_payload,
                    context_features=bandit_context_features,
                    base_weights=base_weights,
                    current_weights=dynamic_weights,
                    top_n=int(settings.bandit_routing_top_n),
                    max_boost=float(settings.bandit_routing_max_boost),
                    decay=float(settings.bandit_routing_rank_decay),
                    min_samples_per_arm=int(settings.bandit_routing_min_samples_per_arm),
                    apply_during_exploration=bool(
                        settings.bandit_routing_apply_during_exploration
                    ),
                )
                if policy_result is not None:
                    effective_dynamic_weights = policy_result.dynamic_weights
            except Exception:
                logger.debug(
                    "provider_selector: bandit routing weight mapping skipped (logical_model=%s)",
                    logical_model.logical_id,
                    exc_info=True,
                )
        selected, scored_candidates = choose_upstream(
            logical_model,
            candidates,
            metrics_by_provider,
            logical_model.strategy,
            session=session_obj,
            dynamic_weights=effective_dynamic_weights,
            enable_health_check=settings.enable_provider_health_check,
        )
        ordered_candidates = _build_ordered_candidates(selected, scored_candidates)
        return ProviderSelectionResult(
            logical_model=logical_model,
            ordered_candidates=ordered_candidates,
            scored_candidates=scored_candidates,
            base_weights=base_weights,
        )

    async def _resolve_logical_model(
        self,
        *,
        requested_model: Any,
        lookup_model_id: str,
        api_style: str,
        allowed_provider_ids: set[str],
        user_id: UUID | None,
        is_superuser: bool,
    ) -> LogicalModel:
        # 1) Static logical model in Redis.
        logical_model = await get_logical_model(self.redis, lookup_model_id)
        if logical_model is not None:
            return logical_model

        # 2) Dynamic build from provider /models caches (cache miss 才会打远端).
        built = await _build_dynamic_logical_model_for_group(
            client=self.client,
            redis=self.redis,
            requested_model=requested_model,
            lookup_model_id=lookup_model_id,
            api_style=api_style,
            db=self.db,
            allowed_provider_ids=allowed_provider_ids,
            user_id=user_id,
            is_superuser=is_superuser,
        )
        if built is None:
            requested_model_str = (
                str(requested_model) if isinstance(requested_model, str) else None
            )
            model_ids_to_check: list[str] = [lookup_model_id]
            if requested_model_str and requested_model_str not in model_ids_to_check:
                model_ids_to_check.append(requested_model_str)
            if self._is_any_model_disabled(
                model_ids=model_ids_to_check, provider_ids=allowed_provider_ids
            ):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail={"message": "该模型已被禁用"},
                )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "message": (
                        f"Requested model '{requested_model}' is not available "
                        "in any configured provider"
                    )
                },
            )
        return built


__all__ = ["ProviderSelectionResult", "ProviderSelector"]
