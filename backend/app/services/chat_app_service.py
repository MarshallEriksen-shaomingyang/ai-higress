from __future__ import annotations

import json
import re
import time
import uuid
from collections.abc import AsyncIterator
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.logging_config import logger
from app.repositories.chat_repository import (
    delete_message,
    get_assistant_message,
    get_last_run_for_message,
    get_previous_user_message,
    persist_run,
    refresh_run,
    save_conversation_title,
)
from app.repositories.run_event_repository import append_run_event
from app.services.bridge_gateway_client import BridgeGatewayClient
from app.services.bridge_tool_runner import (
    bridge_tools_by_agent_to_openai_tools,
    invoke_bridge_tool_and_wait,
)
from app.services.run_event_bus import build_run_event_envelope, publish_run_event_best_effort
from app.services.tool_loop_runner import ToolLoopRunner, split_text_into_deltas

try:
    from redis.asyncio import Redis
except ModuleNotFoundError:  # pragma: no cover
    Redis = object  # type: ignore

from app.api.v1.chat.provider_selector import ProviderSelector
from app.api.v1.chat.request_handler import RequestHandler
from app.auth import AuthenticatedAPIKey
from app.errors import bad_request
from app.jwt_auth import AuthenticatedUser
from app.models import APIKey, Message, Run
from app.services.bandit_policy_service import recommend_challengers
from app.services.chat_history_service import (
    create_assistant_message_after_user,
    create_assistant_message_placeholder_after_user,
    create_user_message,
    finalize_assistant_message_after_user_sequence,
    get_assistant,
    get_conversation,
)
from app.services.conversation_summary_service import maybe_update_conversation_summary
from app.services.chat_run_service import build_openai_request_payload, create_run_record, execute_run_non_stream
from app.services.chat_memory_retrieval import inject_memory_context_into_messages, maybe_retrieve_user_memory_context
from app.services.context_features_service import build_rule_context_features
from app.services.credit_service import InsufficientCreditsError, ensure_account_usable
from app.services.eval_service import execute_run_stream
from app.services.project_chat_settings_service import DEFAULT_PROJECT_CHAT_MODEL
from app.services.project_eval_config_service import (
    DEFAULT_PROVIDER_SCOPES,
    get_effective_provider_ids_for_user,
    get_or_default_project_eval_config,
    resolve_project_context,
)

PROJECT_INHERIT_SENTINEL = "__project__"


def _log_timing(stage: str, start: float, request_id: str, extra: str = "") -> float:
    """记录阶段耗时并返回当前时间戳，用于性能分析"""
    elapsed_ms = (time.perf_counter() - start) * 1000
    extra_str = f" | {extra}" if extra else ""
    logger.info(
        "[CHAT_TIMING] %s | %s | %.2fms%s",
        request_id,
        stage,
        elapsed_ms,
        extra_str,
        extra={"biz": "chat_timing"},
    )
    return time.perf_counter()


def _encode_sse_event(*, event_type: str, data: Any) -> bytes:
    lines: list[str] = []
    event = str(event_type or "").strip()
    if event:
        lines.append(f"event: {event}")

    if isinstance(data, (bytes, bytearray)):
        payload = data.decode("utf-8", errors="ignore")
        lines.append(f"data: {payload}")
    elif isinstance(data, str):
        lines.append(f"data: {data}")
    else:
        lines.append(f"data: {json.dumps(data, ensure_ascii=False)}")

    return ("\n".join(lines) + "\n\n").encode("utf-8")


def _append_run_event_best_effort(
    db: Session,
    *,
    redis: Redis | None = None,
    run_id: UUID,
    event_type: str,
    payload: dict[str, Any],
) -> None:
    try:
        row = append_run_event(db, run_id=run_id, event_type=event_type, payload=payload)
        created_at_iso = None
        try:
            created_at_iso = row.created_at.isoformat() if getattr(row, "created_at", None) is not None else None
        except Exception:
            created_at_iso = None
        publish_run_event_best_effort(
            redis,
            run_id=run_id,
            envelope=build_run_event_envelope(
                run_id=run_id,
                seq=int(getattr(row, "seq", 0) or 0),
                event_type=str(getattr(row, "event_type", event_type) or event_type),
                created_at_iso=created_at_iso,
                payload=payload,
            ),
        )
    except Exception:  # pragma: no cover - best-effort only
        logger.debug("chat: append_run_event failed (run_id=%s type=%s)", run_id, event_type, exc_info=True)


def _run_to_summary(run) -> dict[str, Any]:
    return {
        "run_id": str(run.id),
        "requested_logical_model": run.requested_logical_model,
        "status": run.status,
        "output_preview": run.output_preview,
        "latency_ms": run.latency_ms,
        "error_code": run.error_code,
        "tool_invocations": getattr(run, "tool_invocations", None),
    }


def _to_authenticated_api_key(
    *,
    api_key: APIKey,
    current_user: AuthenticatedUser,
) -> AuthenticatedAPIKey:
    return AuthenticatedAPIKey(
        id=UUID(str(api_key.id)),
        user_id=UUID(str(api_key.user_id)),
        user_username=current_user.username,
        is_superuser=bool(current_user.is_superuser),
        name=api_key.name,
        is_active=bool(api_key.is_active),
        disabled_reason=api_key.disabled_reason,
        has_provider_restrictions=bool(api_key.has_provider_restrictions),
        allowed_provider_ids=list(api_key.allowed_provider_ids),
    )

_THINK_BLOCK_RE = re.compile(r"<think>[\s\S]*?</think>", re.IGNORECASE)
_THINK_UNCLOSED_RE = re.compile(r"<think>[\s\S]*\Z", re.IGNORECASE)
_THINK_CLOSE_TAG_RE = re.compile(r"</think>", re.IGNORECASE)

# Common wrapping quote pairs for generated titles.
_TITLE_QUOTE_PAIRS: dict[str, str] = {
    '"': '"',
    "'": "'",
    "“": "”",
    "‘": "’",
    "《": "》",
    "「": "」",
    "『": "』",
}

_TOOL_TAG_STREAM_TRIGGER_RE = re.compile(
    r"(FUNC_TRIGGER_[^\s]*?_END|<function_calls>|<function_call>)",
    re.IGNORECASE,
)


class _ToolTagStreamFilter:
    """
    流式场景下的“标签型 tool call”降噪器：
    - 避免把 <function_calls> / FUNC_TRIGGER_* 等工件直接推给前端
    - 只在本次请求确实开启了 tool loop 时启用（避免误伤无工具场景）
    """

    def __init__(self, *, holdback_chars: int = 64) -> None:
        self._holdback = max(0, int(holdback_chars))
        self._buf = ""
        self.detected = False

    def feed(self, chunk: str) -> str:
        if not chunk:
            return ""
        if self.detected:
            return ""

        self._buf += chunk

        if _TOOL_TAG_STREAM_TRIGGER_RE.search(self._buf):
            self.detected = True
            # 丢弃本次缓冲（后续由 tool loop 输出最终答案），避免把标签泄漏给前端。
            self._buf = ""
            return ""

        if self._holdback <= 0:
            out = self._buf
            self._buf = ""
            return out

        if len(self._buf) <= self._holdback:
            return ""
        out = self._buf[:-self._holdback]
        self._buf = self._buf[-self._holdback :]
        return out

    def flush(self) -> str:
        if self.detected:
            self._buf = ""
            return ""
        out = self._buf
        self._buf = ""
        return out


def _strip_think_blocks(value: str) -> str:
    if not value:
        return ""
    text = value
    # First remove well-formed <think>...</think> blocks.
    text = _THINK_BLOCK_RE.sub(" ", text)
    # Then remove any leftover unclosed <think>... tail (common in some reasoning models).
    text = _THINK_UNCLOSED_RE.sub(" ", text)
    # Finally remove any stray closing tags.
    text = _THINK_CLOSE_TAG_RE.sub(" ", text)
    return " ".join(text.split()).strip()


def _sanitize_conversation_title(value: str) -> str:
    title = _strip_think_blocks(value or "").strip()
    if not title:
        return ""

    # Remove common wrapping quotes
    while len(title) >= 2:
        first = title[0]
        last = title[-1]
        expected_last = _TITLE_QUOTE_PAIRS.get(first)
        if expected_last is None or expected_last != last:
            break
        title = title[1:-1].strip()

    # Collapse whitespace
    title = " ".join(title.split())

    # Conservative max length (DB: 255)
    if len(title) > 60:
        title = title[:60].rstrip()
    return title


def _extract_first_choice_text(payload: dict[str, Any] | None) -> str | None:
    if not isinstance(payload, dict):
        return None
    choices = payload.get("choices")
    if not isinstance(choices, list) or not choices:
        return None
    first = choices[0]
    if not isinstance(first, dict):
        return None
    message = first.get("message")
    if isinstance(message, dict):
        content = message.get("content")
        if isinstance(content, str) and content.strip():
            return content
    content = first.get("text")
    if isinstance(content, str) and content.strip():
        return content
    return None


async def _resolve_final_model(
    db: Session,
    redis: Redis,
    client: Any,
    current_user: AuthenticatedUser,
    ctx: Any,
    assistant: Any,
    requested_model: str,
    user_text: str | None,
    model_preset: dict | None,
) -> str:
    """
    统一处理模型解析逻辑：
    1. 处理 PROJECT_INHERIT_SENTINEL
    2. 处理 'auto' 模式（Candidate 检查 + Bandit 推荐）
    3. 返回最终确定的 logical_model
    """
    final_model = requested_model
    if final_model == PROJECT_INHERIT_SENTINEL:
        final_model = (
            (getattr(ctx.api_key, "chat_default_logical_model", None) or "").strip() or DEFAULT_PROJECT_CHAT_MODEL
        )

    if not final_model:
        raise bad_request("未指定模型")

    if final_model != "auto":
        return final_model

    # Auto mode logic
    cfg = get_or_default_project_eval_config(db, project_id=ctx.project_id)
    candidates = list(cfg.candidate_logical_models or [])
    if not candidates:
        raise bad_request(
            "当前助手默认模型为 auto，但项目未配置 candidate_logical_models",
            details={"project_id": str(ctx.project_id)},
        )

    preset_payload: dict[str, Any] = {}
    if isinstance(assistant.model_preset, dict):
        preset_payload.update(assistant.model_preset)
    if isinstance(model_preset, dict):
        preset_payload.update(model_preset)

    effective_provider_ids = get_effective_provider_ids_for_user(
        db,
        user_id=UUID(str(current_user.id)),
        api_key=ctx.api_key,
        provider_scopes=list(getattr(cfg, "provider_scopes", None) or DEFAULT_PROVIDER_SCOPES),
    )

    selector = ProviderSelector(client=client, redis=redis, db=db)
    available_candidates = await selector.check_candidate_availability(
        candidate_logical_models=candidates,
        effective_provider_ids=effective_provider_ids,
        api_style="openai",
        user_id=UUID(str(current_user.id)),
        is_superuser=current_user.is_superuser,
        request_payload=preset_payload or None,
        budget_credits=cfg.budget_per_eval_credits,
    )

    if not available_candidates:
        raise bad_request(
            "auto 模式下无可用的候选模型（均被禁用或无健康上游）",
            details={"project_id": str(ctx.project_id)},
        )

    rec = recommend_challengers(
        db,
        project_id=ctx.project_id,
        assistant_id=UUID(str(assistant.id)),
        baseline_logical_model="auto",
        user_text=user_text or "",
        context_features=build_rule_context_features(user_text=user_text or "", request_payload=None),
        candidate_logical_models=available_candidates,
        k=1,
        policy_version="ts-v1",
    )

    if not rec.candidates:
        raise bad_request(
            "auto 模式下无法选择候选模型",
            details={"project_id": str(ctx.project_id)},
        )
    
    return rec.candidates[0].logical_model


async def _load_bridge_tools_for_payload(
    base_payload: dict[str, Any],
    bridge_agent_id: str | None,
    bridge_agent_ids: list[str] | None,
    bridge_tool_selections: list[dict] | None,
) -> tuple[dict[str, Any], list[str], dict[str, set[str]], list[dict[str, Any]], dict[str, tuple[str, str]]]:
    """
    统一处理 Bridge 工具加载逻辑：
    1. 解析 agent ids
    2. 调用 BridgeGateway 获取工具
    3. 过滤白名单
    4. 转换为 OpenAI 工具格式
    5. 更新 payload
    """
    effective_ids, tool_filters = _normalize_bridge_inputs(
        bridge_agent_id=bridge_agent_id,
        bridge_agent_ids=bridge_agent_ids,
        bridge_tool_selections=bridge_tool_selections,
    )
    
    if not effective_ids:
        return base_payload, [], {}, [], {}

    bridge_tools_by_agent: dict[str, list[dict[str, Any]]] = {}
    openai_tools: list[dict[str, Any]] = []
    tool_name_map: dict[str, tuple[str, str]] = {}

    try:
        bridge = BridgeGatewayClient()
        for aid in effective_ids:
            try:
                tools_resp = await bridge.list_tools(aid)
            except Exception:
                continue
            
            if isinstance(tools_resp, dict) and isinstance(tools_resp.get("tools"), list):
                tools = [t for t in tools_resp["tools"] if isinstance(t, dict)]
                allowlist = tool_filters.get(aid)
                if allowlist:
                    tools = [t for t in tools if str(t.get("name") or "").strip() in allowlist]
                if tools:
                    bridge_tools_by_agent[aid] = tools

        openai_tools, tool_name_map = bridge_tools_by_agent_to_openai_tools(
            bridge_tools_by_agent=bridge_tools_by_agent
        )
        
        new_payload = dict(base_payload)
        if openai_tools:
            new_payload["tools"] = openai_tools
            new_payload["tool_choice"] = "auto"
        
        return new_payload, effective_ids, tool_filters, openai_tools, tool_name_map

    except Exception:
        # Best-effort fallback
        return base_payload, effective_ids, tool_filters, [], {}


def _create_standard_tool_loop_runner(
    db: Session,
    redis: Redis,
    client: Any,
    auth_key: AuthenticatedAPIKey,
    effective_provider_ids: set[str],
    conversation_id: str,
    assistant_id: UUID | None,
    requested_model: str,
    run_id: UUID,
) -> ToolLoopRunner:
    async def _invoke_tool(req_id: str, agent_id: str, tool_name: str, arguments: dict[str, Any]):
        return await invoke_bridge_tool_and_wait(
            req_id=req_id,
            agent_id=agent_id,
            tool_name=tool_name,
            arguments=arguments,
            timeout_ms=60_000,
            result_timeout_seconds=120.0,
        )

    async def _cancel_tool(req_id: str, agent_id: str, reason: str) -> None:
        bridge = BridgeGatewayClient()
        await bridge.cancel(req_id=req_id, agent_id=agent_id, reason=reason)

    async def _call_model(follow_payload: dict[str, Any], idempotency_key: str) -> dict[str, Any] | None:
        handler = RequestHandler(api_key=auth_key, db=db, redis=redis, client=client)
        resp = await handler.handle(
            payload=follow_payload,
            requested_model=requested_model,
            lookup_model_id=requested_model,
            api_style="openai",
            effective_provider_ids=effective_provider_ids,
            session_id=conversation_id,
            assistant_id=assistant_id,
            billing_reason="chat_tool_loop",
            idempotency_key=idempotency_key or None,
        )
        try:
            raw = resp.body.decode("utf-8", errors="ignore")
            parsed = json.loads(raw)
            if isinstance(parsed, dict):
                return parsed
        except Exception:
            return None
        return None

    return ToolLoopRunner(
        invoke_tool=_invoke_tool,
        call_model=_call_model,
        cancel_tool=_cancel_tool,
        event_sink=lambda et, p: _append_run_event_best_effort(
            db,
            redis=redis,
            run_id=run_id,
            event_type=et,
            payload=p,
        ),
    )


def _normalize_bridge_inputs(
    *,
    bridge_agent_id: str | None,
    bridge_agent_ids: list[str] | None,
    bridge_tool_selections: list[dict] | None,
    max_agents: int = 5,
) -> tuple[list[str], dict[str, set[str]]]:
    """
    合并 bridge 相关输入：
    - 返回去重后的有效 Agent 列表（按出现顺序，最多 max_agents）
    - 返回每个 Agent 的工具白名单（若未指定则空）
    """
    effective_ids: list[str] = []
    seen: set[str] = set()

    def _add_agent(value: str | None) -> None:
        if not value:
            return
        trimmed = str(value).strip()
        if trimmed and trimmed not in seen:
            effective_ids.append(trimmed)
            seen.add(trimmed)

    if isinstance(bridge_agent_ids, list):
        for aid in bridge_agent_ids:
            _add_agent(aid)
    _add_agent(bridge_agent_id)

    tool_filters: dict[str, set[str]] = {}
    if isinstance(bridge_tool_selections, list):
        for sel in bridge_tool_selections:
            if isinstance(sel, dict):
                agent = str(sel.get("agent_id") or "").strip()
                raw_names = sel.get("tool_names")
            else:
                agent = str(getattr(sel, "agent_id", "") or "").strip()
                raw_names = getattr(sel, "tool_names", None)
            if not agent:
                continue
            names: list[str] = []
            if isinstance(raw_names, list):
                for n in raw_names:
                    val = str(n).strip()
                    if val:
                        names.append(val)
            if names:
                _add_agent(agent)
                # 限制每个 agent 的工具白名单数量，防止过大注入
                tool_filters[agent] = set(names[:30])

    if len(effective_ids) > max_agents:
        effective_ids = effective_ids[:max_agents]

    tool_filters = {aid: names for aid, names in tool_filters.items() if aid in effective_ids}

    return effective_ids, tool_filters


def _truncate_title_input(value: str, *, max_len: int = 1000) -> str:
    text = (value or "").strip()
    if not text:
        return ""
    if len(text) <= max_len:
        return text
    return text[:max_len].rstrip()


def _enqueue_auto_title_task(
    *,
    conversation_id: UUID,
    message_id: UUID,
    user_id: UUID,
    assistant_id: UUID,
    requested_model_for_title_fallback: str | None,
) -> None:
    """
    将自动标题生成任务异步入队（Celery）。

    仅在满足条件（首条消息且标题为空）时调用。
    """
    try:
        from app.celery_app import celery_app

        celery_app.send_task(
            "tasks.generate_conversation_title",
            args=[
                str(conversation_id),
                str(message_id),
                str(user_id),
                str(assistant_id),
                requested_model_for_title_fallback or "",
            ],
        )
    except Exception as exc:  # pragma: no cover - 入队失败不影响主流程
        logger.warning("enqueue auto_title task failed: %s", exc, exc_info=exc)


def _enqueue_chat_run_task(
    *,
    run_id: UUID,
    assistant_message_id: UUID | None,
    effective_bridge_agent_ids: list[str],
    streaming: bool,
) -> None:
    """
    将 chat run 执行任务异步入队（Celery）。
    """
    try:
        from app.celery_app import celery_app

        celery_app.send_task(
            "tasks.execute_chat_run",
            args=[
                str(run_id),
                str(assistant_message_id) if assistant_message_id is not None else None,
                list(effective_bridge_agent_ids or []),
                bool(streaming),
            ],
        )
    except Exception as exc:  # pragma: no cover - 入队失败不影响主流程（由上层决定是否降级/报错）
        logger.warning("enqueue chat_run task failed: %s", exc, exc_info=exc)


def _append_run_event_and_publish(
    db: Session,
    *,
    redis: Redis | None,
    run_id: UUID,
    event_type: str,
    payload: dict[str, Any],
) -> int | None:
    """
    写入 RunEvent 真相并发布到 Redis 热通道。
    返回写入后的 seq（失败则返回 None）。
    """
    try:
        row = append_run_event(db, run_id=run_id, event_type=event_type, payload=payload)
        created_at_iso = None
        try:
            created_at_iso = row.created_at.isoformat() if getattr(row, "created_at", None) is not None else None
        except Exception:
            created_at_iso = None
        publish_run_event_best_effort(
            redis,
            run_id=run_id,
            envelope=build_run_event_envelope(
                run_id=run_id,
                seq=int(getattr(row, "seq", 0) or 0),
                event_type=str(getattr(row, "event_type", event_type) or event_type),
                created_at_iso=created_at_iso,
                payload=payload,
            ),
        )
        return int(getattr(row, "seq", 0) or 0)
    except Exception:  # pragma: no cover - best-effort only
        logger.debug("chat: append_run_event failed (run_id=%s type=%s)", run_id, event_type, exc_info=True)
        return None


async def create_message_and_queue_baseline_run(
    db: Session,
    *,
    redis: Redis,
    client: Any,
    current_user: AuthenticatedUser,
    conversation_id: UUID,
    content: str | None,
    input_audio: dict | None = None,
    streaming: bool,
    override_logical_model: str | None = None,
    model_preset: dict | None = None,
    bridge_agent_id: str | None = None,
    bridge_agent_ids: list[str] | None = None,
    bridge_tool_selections: list[dict] | None = None,
) -> tuple[UUID, UUID, UUID | None, dict[str, Any], int, list[str]]:
    """
    只做“创建 message + 创建 queued run + 写入 message.created 事件 + 入队 Celery 执行”。

    返回：
      (user_message_id, run_id, assistant_message_id_or_none, message_created_payload, created_seq, effective_bridge_agent_ids)
    """
    conv = get_conversation(db, conversation_id=conversation_id, user_id=UUID(str(current_user.id)))
    ctx = resolve_project_context(db, project_id=UUID(str(conv.api_key_id)), current_user=current_user)

    try:
        ensure_account_usable(db, user_id=UUID(str(current_user.id)))
    except InsufficientCreditsError as exc:
        raise bad_request(
            "积分不足",
            details={"code": "CREDIT_NOT_ENOUGH", "balance": exc.balance},
        )

    assistant = get_assistant(db, assistant_id=UUID(str(conv.assistant_id)), user_id=UUID(str(current_user.id)))
    
    requested_model = override_logical_model or assistant.default_logical_model
    requested_model = await _resolve_final_model(
        db=db,
        redis=redis,
        client=client,
        current_user=current_user,
        ctx=ctx,
        assistant=assistant,
        requested_model=requested_model,
        user_text=(content or ""),
        model_preset=model_preset,
    )

    user_message = create_user_message(db, conversation=conv, content_text=content, input_audio=input_audio)
    assistant_message: Message | None = None
    if streaming:
        assistant_message = create_assistant_message_placeholder_after_user(
            db,
            conversation_id=UUID(str(conv.id)),
            user_sequence=int(user_message.sequence or 0),
        )

    payload = build_openai_request_payload(
        db,
        conversation=conv,
        assistant=assistant,
        user_message=user_message,
        requested_logical_model=requested_model,
        model_preset_override=model_preset,
    )

    payload, effective_bridge_agent_ids, _tool_filters, _openai_tools, _tool_name_map = await _load_bridge_tools_for_payload(
        base_payload=payload,
        bridge_agent_id=bridge_agent_id,
        bridge_agent_ids=bridge_agent_ids,
        bridge_tool_selections=bridge_tool_selections,
    )

    run = create_run_record(
        db,
        user_id=UUID(str(current_user.id)),
        api_key_id=ctx.project_id,
        message_id=UUID(str(user_message.id)),
        requested_logical_model=requested_model,
        request_payload=payload,
        status="queued",
    )

    # 首问自动标题（入队即可，不依赖 run 执行完成）
    try:
        if int(user_message.sequence or 0) == 1 and not (conv.title or "").strip():
            _enqueue_auto_title_task(
                conversation_id=UUID(str(conv.id)),
                message_id=UUID(str(user_message.id)),
                user_id=UUID(str(current_user.id)),
                assistant_id=UUID(str(assistant.id)),
                requested_model_for_title_fallback=requested_model,
            )
    except Exception:  # pragma: no cover
        pass

    if streaming:
        created_payload: dict[str, Any] = {
            "type": "message.created",
            "conversation_id": str(conv.id),
            "user_message_id": str(user_message.id),
            "assistant_message_id": str(assistant_message.id) if assistant_message is not None else None,
            "baseline_run": _run_to_summary(run),
        }
    else:
        created_payload = {
            "type": "message.created",
            "conversation_id": str(conv.id),
            "user_message_id": str(user_message.id),
            "run_id": str(run.id),
        }

    created_seq = _append_run_event_and_publish(
        db,
        redis=redis,
        run_id=UUID(str(run.id)),
        event_type="message.created",
        payload=created_payload,
    ) or 0

    _enqueue_chat_run_task(
        run_id=UUID(str(run.id)),
        assistant_message_id=UUID(str(assistant_message.id)) if assistant_message is not None else None,
        effective_bridge_agent_ids=effective_bridge_agent_ids,
        streaming=streaming,
    )

    return (
        UUID(str(user_message.id)),
        UUID(str(run.id)),
        UUID(str(assistant_message.id)) if assistant_message is not None else None,
        created_payload,
        int(created_seq),
        effective_bridge_agent_ids,
    )


async def _maybe_auto_title_conversation(
    db: Session,
    *,
    redis: Redis,
    client: Any,
    current_user: AuthenticatedUser,
    conv: Any,
    assistant: Any,
    effective_provider_ids: set[str],
    user_text: str,
    user_sequence: int,
    requested_model_for_title_fallback: str,
) -> None:
    """
    在首条 user 消息发送后，若会话尚无 title，则尝试用“标题模型”自动生成标题（尽力而为）。
    """
    if (conv.title or "").strip():
        return

    # Only auto-title on first user message (sequence=1)
    if int(user_sequence or 0) != 1:
        return

    try:
        # Optional second check: avoid going negative right after baseline if credit check is enabled.
        ensure_account_usable(db, user_id=UUID(str(current_user.id)))
    except InsufficientCreditsError:
        return
    except Exception:
        # Credit check failures should never block message sending.
        return

    # Use the same project context for billing/provider access.
    ctx = resolve_project_context(db, project_id=UUID(str(conv.api_key_id)), current_user=current_user)

    title_model_raw = (getattr(assistant, "title_logical_model", None) or "").strip()
    if not title_model_raw:
        title_model_raw = (getattr(assistant, "default_logical_model", None) or "").strip()
    if not title_model_raw:
        title_model_raw = (requested_model_for_title_fallback or "").strip()
    if not title_model_raw:
        return

    if title_model_raw == PROJECT_INHERIT_SENTINEL:
        title_model_raw = (getattr(ctx.api_key, "chat_title_logical_model", None) or "").strip()
        if not title_model_raw:
            return

    title_model = requested_model_for_title_fallback if title_model_raw == "auto" else title_model_raw
    if not title_model:
        return

    system_prompt = (
        "You are a conversation title generator.\n"
        "Task: Generate a short title for the conversation based on the user's FIRST message.\n"
        "Language: The title MUST be in the same language as the user's message (match script/locale). "
        "If the user's message is mixed-language, use the dominant language.\n"
        "Rules:\n"
        "- Output ONLY the title.\n"
        "- Do NOT output any <think> blocks or reasoning.\n"
        "- No quotes, no markdown, no emojis, no extra punctuation at the end.\n"
        "- Single line.\n"
        "- Length: <= 20 CJK characters OR <= 8 English words; for other languages keep it short (<= 10 words).\n"
    )

    user_text = _truncate_title_input(user_text, max_len=1000)
    if not user_text:
        return

    payload: dict[str, Any] = {
        "model": title_model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_text},
        ],
        "temperature": 0.2,
        "max_tokens": 48,
    }

    auth_key = _to_authenticated_api_key(api_key=ctx.api_key, current_user=current_user)

    handler = RequestHandler(api_key=auth_key, db=db, redis=redis, client=client)
    resp = await handler.handle(
        payload=payload,
        requested_model=title_model,
        lookup_model_id=title_model,
        api_style="openai",
        effective_provider_ids=effective_provider_ids,
        session_id=str(conv.id),
        assistant_id=UUID(str(getattr(assistant, "id", None))) if getattr(assistant, "id", None) else None,
        billing_reason="conversation_title",
    )

    if int(getattr(resp, "status_code", 500)) >= 400:
        return

    response_payload: dict[str, Any] | None = None
    try:
        raw = resp.body.decode("utf-8", errors="ignore")
        parsed = json.loads(raw)
        if isinstance(parsed, dict):
            response_payload = parsed
    except Exception:
        response_payload = None

    raw_title = _extract_first_choice_text(response_payload)
    title = _sanitize_conversation_title(raw_title or "")
    if not title:
        return

    save_conversation_title(db, conversation=conv, title=title)


async def send_message_and_run_baseline(
    db: Session,
    *,
    redis: Redis,
    client: Any,
    current_user: AuthenticatedUser,
    conversation_id: UUID,
    content: str | None,
    input_audio: dict | None = None,
    override_logical_model: str | None = None,
    model_preset: dict | None = None,
    bridge_agent_id: str | None = None,
    bridge_agent_ids: list[str] | None = None,
    bridge_tool_selections: list[dict] | None = None,
) -> tuple[UUID, UUID]:
    """
    创建 user message 并同步执行 baseline run，随后写入 assistant message（用于历史上下文）。

    Returns:
        (message_id, baseline_run_id)
    """
    # === 性能计时开始 ===
    request_id = f"msg_{uuid.uuid4().hex[:8]}"
    t_total_start = time.perf_counter()
    t_stage = t_total_start
    logger.info("[CHAT_TIMING] %s | START | non-stream conversation_id=%s", request_id, conversation_id)

    conv = get_conversation(db, conversation_id=conversation_id, user_id=UUID(str(current_user.id)))
    ctx = resolve_project_context(db, project_id=UUID(str(conv.api_key_id)), current_user=current_user)
    t_stage = _log_timing("1_get_conversation_context", t_stage, request_id)

    # 余额校验（沿用网关规则）
    try:
        ensure_account_usable(db, user_id=UUID(str(current_user.id)))
    except InsufficientCreditsError as exc:
        raise bad_request(
            "积分不足",
            details={"code": "CREDIT_NOT_ENOUGH", "balance": exc.balance},
        )
    t_stage = _log_timing("2_ensure_account_usable", t_stage, request_id)

    assistant = get_assistant(db, assistant_id=UUID(str(conv.assistant_id)), user_id=UUID(str(current_user.id)))
    
    requested_model = override_logical_model or assistant.default_logical_model
    t_stage = _log_timing("3_get_assistant_model", t_stage, request_id, f"model={requested_model}")

    cfg = get_or_default_project_eval_config(db, project_id=ctx.project_id)

    effective_provider_ids = get_effective_provider_ids_for_user(
        db,
        user_id=UUID(str(current_user.id)),
        api_key=ctx.api_key,
        provider_scopes=list(getattr(cfg, "provider_scopes", None) or DEFAULT_PROVIDER_SCOPES),
    )
    t_stage = _log_timing("4_get_provider_ids", t_stage, request_id, f"count={len(effective_provider_ids)}")

    requested_model = await _resolve_final_model(
        db=db,
        redis=redis,
        client=client,
        current_user=current_user,
        ctx=ctx,
        assistant=assistant,
        requested_model=requested_model,
        user_text=(content or ""),
        model_preset=model_preset,
    )
    t_stage = _log_timing("5_auto_model_selection", t_stage, request_id, f"selected={requested_model}")

    user_message = create_user_message(db, conversation=conv, content_text=content, input_audio=input_audio)
    t_stage = _log_timing("6_create_user_message", t_stage, request_id)

    payload = build_openai_request_payload(
        db,
        conversation=conv,
        assistant=assistant,
        user_message=user_message,
        requested_logical_model=requested_model,
        model_preset_override=model_preset,
    )
    t_stage = _log_timing("7_build_payload", t_stage, request_id, f"messages_count={len(payload.get('messages', []))}")

    # Read path: best-effort memory retrieval (default-not-retrieve, gated).
    try:
        auth_key = _to_authenticated_api_key(api_key=ctx.api_key, current_user=current_user)
        mem_ctx = await maybe_retrieve_user_memory_context(
            db,
            redis=redis,
            client=client,
            api_key=auth_key,
            effective_provider_ids=effective_provider_ids,
            owner_user_id=UUID(str(current_user.id)),
            project_id=UUID(str(ctx.project_id)),
            user_text=(content or ""),
            summary_text=getattr(conv, "summary_text", None),
            top_k=3,
            idempotency_key=f"mem_read:{conv.id}:{user_message.id}",
        )
        if mem_ctx:
            payload["messages"] = inject_memory_context_into_messages(
                list(payload.get("messages", []) or []),
                memory_context=mem_ctx,
            )
    except Exception:  # pragma: no cover - best-effort only
        pass

    t_bridge_start = time.perf_counter()
    payload, effective_bridge_agent_ids, _tool_filters, openai_tools, tool_name_map = await _load_bridge_tools_for_payload(
        base_payload=payload,
        bridge_agent_id=bridge_agent_id,
        bridge_agent_ids=bridge_agent_ids,
        bridge_tool_selections=bridge_tool_selections,
    )
    t_stage = _log_timing("8_load_bridge_tools", t_bridge_start, request_id, f"agents={len(effective_bridge_agent_ids)} tools={len(openai_tools)}")

    run = create_run_record(
        db,
        user_id=UUID(str(current_user.id)),
        api_key_id=ctx.project_id,
        message_id=UUID(str(user_message.id)),
        requested_logical_model=requested_model,
        request_payload=payload,
    )
    t_stage = _log_timing("9_create_run_record", t_stage, request_id)
    _append_run_event_best_effort(
        db,
        redis=redis,
        run_id=UUID(str(run.id)),
        event_type="message.created",
        payload={
            "type": "message.created",
            "conversation_id": str(conv.id),
            "user_message_id": str(user_message.id),
            "run_id": str(run.id),
        },
    )

    auth_key = _to_authenticated_api_key(api_key=ctx.api_key, current_user=current_user)
    t_upstream_start = time.perf_counter()
    run = await execute_run_non_stream(
        db,
        redis=redis,
        client=client,
        api_key=auth_key,
        effective_provider_ids=effective_provider_ids,
        conversation=conv,
        assistant=assistant,
        user_message=user_message,
        run=run,
        requested_logical_model=requested_model,
        model_preset_override=model_preset,
        payload_override=payload,
    )
    t_stage = _log_timing("10_execute_run_upstream", t_upstream_start, request_id, f"status={run.status} provider={run.selected_provider_id}")

    # Tool-calling loop（兼容模式：仍是请求内执行，但过程写入 RunEvent 作为真相）。
    if run.status == "succeeded" and effective_bridge_agent_ids and openai_tools:
        t_tool_loop_start = time.perf_counter()
        tool_loop_provider_ids = effective_provider_ids
        pinned_provider_id = str(getattr(run, "selected_provider_id", None) or "").strip()
        if pinned_provider_id and pinned_provider_id in tool_loop_provider_ids:
            tool_loop_provider_ids = {pinned_provider_id}

        runner = _create_standard_tool_loop_runner(
            db=db,
            redis=redis,
            client=client,
            auth_key=auth_key,
            effective_provider_ids=tool_loop_provider_ids,
            conversation_id=str(conv.id),
            assistant_id=UUID(str(getattr(assistant, "id", None))) if getattr(assistant, "id", None) else None,
            requested_model=requested_model,
            run_id=UUID(str(run.id)),
        )

        result = await runner.run(
            conversation_id=str(conv.id),
            run_id=str(run.id),
            base_payload=payload,
            first_response_payload=getattr(run, "response_payload", None),
            effective_bridge_agent_ids=effective_bridge_agent_ids,
            tool_name_map=tool_name_map,
            user_message_id=str(user_message.id),
            idempotency_prefix=f"chat:{run.id}:tool_loop",
        )

        t_stage = _log_timing(
            "11_tool_loop",
            t_tool_loop_start,
            request_id,
            f"did_run={result.did_run} invocations={len(result.tool_invocations)} error={result.error_code or ''}",
        )

        if result.did_run:
            output_text = result.output_text
            if result.error_code:
                run.status = "failed"
                run.error_code = result.error_code
                run.error_message = result.error_message
            elif output_text and output_text.strip():
                run.output_text = output_text
                run.output_preview = output_text.strip()[:380].rstrip()
            else:
                run.status = "failed"
                run.error_code = "TOOL_LOOP_FAILED"
                run.error_message = "tool loop finished without assistant content"

            run.response_payload = {
                "bridge": {
                    "agent_ids": effective_bridge_agent_ids,
                    "tool_invocations": result.tool_invocations,
                },
                "first_response": result.first_response_payload,
                "final_response": result.final_response_payload,
            }
            run = persist_run(db, run)

    assistant_msg: Message | None = None
    # baseline 成功时写入 assistant message，作为后续上下文
    if run.status == "succeeded" and run.output_text:
        assistant_msg = create_assistant_message_after_user(
            db,
            conversation_id=UUID(str(conv.id)),
            user_sequence=int(user_message.sequence or 0),
            content_text=run.output_text,
        )
        try:
            await maybe_update_conversation_summary(
                db,
                redis=redis,
                client=client,
                api_key=auth_key,
                effective_provider_ids=effective_provider_ids,
                conversation_id=UUID(str(conv.id)),
                assistant_id=UUID(str(getattr(assistant, "id", None))) if getattr(assistant, "id", None) else None,
                requested_logical_model=requested_model,
                new_until_sequence=int(getattr(assistant_msg, "sequence", 0) or 0),
            )
        except Exception:  # pragma: no cover - best-effort only
            logger.debug(
                "chat_app: conversation summary update failed (conversation_id=%s)",
                str(conv.id),
                exc_info=True,
            )
    t_stage = _log_timing("11_save_assistant_message", t_stage, request_id)
    _append_run_event_best_effort(
        db,
        redis=redis,
        run_id=UUID(str(run.id)),
        event_type="message.completed" if run.status == "succeeded" else "message.failed",
        payload={
            "type": "message.completed" if run.status == "succeeded" else "message.failed",
            "conversation_id": str(conv.id),
            "user_message_id": str(user_message.id),
            "assistant_message_id": str(assistant_msg.id) if assistant_msg is not None else None,
            "baseline_run": _run_to_summary(run),
            "output_text": run.output_text if run.status == "succeeded" else None,
        },
    )

    # Auto-title conversation based on the first user question（异步入队，避免阻塞主流程）
    t_title_start = time.perf_counter()
    try:
        if int(user_message.sequence or 0) == 1 and not (conv.title or "").strip():
            _enqueue_auto_title_task(
                conversation_id=UUID(str(conv.id)),
                message_id=UUID(str(user_message.id)),
                user_id=UUID(str(current_user.id)),
                assistant_id=UUID(str(assistant.id)),
                requested_model_for_title_fallback=requested_model,
            )
            _log_timing("12_auto_title_enqueued", t_title_start, request_id)
    except Exception:  # pragma: no cover - best-effort only
        # Never break the main chat flow for title generation.
        pass

    # === 性能计时结束 ===
    total_ms = (time.perf_counter() - t_total_start) * 1000
    logger.info("[CHAT_TIMING] %s | TOTAL | %.2fms | model=%s provider=%s status=%s",
                request_id, total_ms, requested_model, run.selected_provider_id, run.status)

    return UUID(str(user_message.id)), UUID(str(run.id))


async def stream_message_and_run_baseline(
    db: Session,
    *,
    redis: Redis,
    client: Any,
    current_user: AuthenticatedUser,
    conversation_id: UUID,
    content: str | None,
    input_audio: dict | None = None,
    override_logical_model: str | None = None,
    model_preset: dict | None = None,
    bridge_agent_id: str | None = None,
    bridge_agent_ids: list[str] | None = None,
    bridge_tool_selections: list[dict] | None = None,
) -> AsyncIterator[bytes]:
    """
    创建 user message 并以 SSE 流式执行 baseline run。

    注意：流式模式同样支持 bridge 工具调用（tool loop 在流式回复结束后进行补充调用）。
    """
    # === 性能计时开始 ===
    request_id = f"stream_{uuid.uuid4().hex[:8]}"
    t_total_start = time.perf_counter()
    t_stage = t_total_start
    logger.info("[CHAT_TIMING] %s | START | stream conversation_id=%s", request_id, conversation_id)

    conv = get_conversation(db, conversation_id=conversation_id, user_id=UUID(str(current_user.id)))
    ctx = resolve_project_context(db, project_id=UUID(str(conv.api_key_id)), current_user=current_user)
    t_stage = _log_timing("1_get_conversation_context", t_stage, request_id)

    try:
        ensure_account_usable(db, user_id=UUID(str(current_user.id)))
    except InsufficientCreditsError as exc:
        raise bad_request(
            "积分不足",
            details={"code": "CREDIT_NOT_ENOUGH", "balance": exc.balance},
        )
    t_stage = _log_timing("2_ensure_account_usable", t_stage, request_id)

    assistant = get_assistant(db, assistant_id=UUID(str(conv.assistant_id)), user_id=UUID(str(current_user.id)))
    
    requested_model = override_logical_model or assistant.default_logical_model
    t_stage = _log_timing("3_get_assistant_model", t_stage, request_id, f"model={requested_model}")

    cfg = get_or_default_project_eval_config(db, project_id=ctx.project_id)
    effective_provider_ids = get_effective_provider_ids_for_user(
        db,
        user_id=UUID(str(current_user.id)),
        api_key=ctx.api_key,
        provider_scopes=list(getattr(cfg, "provider_scopes", None) or DEFAULT_PROVIDER_SCOPES),
    )
    t_stage = _log_timing("4_get_provider_ids", t_stage, request_id, f"count={len(effective_provider_ids)}")

    requested_model = await _resolve_final_model(
        db=db,
        redis=redis,
        client=client,
        current_user=current_user,
        ctx=ctx,
        assistant=assistant,
        requested_model=requested_model,
        user_text=(content or ""),
        model_preset=model_preset,
    )
    t_stage = _log_timing("5_auto_model_selection", t_stage, request_id, f"selected={requested_model}")

    user_message = create_user_message(db, conversation=conv, content_text=content, input_audio=input_audio)
    assistant_message = create_assistant_message_placeholder_after_user(
        db,
        conversation_id=UUID(str(conv.id)),
        user_sequence=int(user_message.sequence or 0),
    )
    t_stage = _log_timing("6_create_messages", t_stage, request_id)

    payload = build_openai_request_payload(
        db,
        conversation=conv,
        assistant=assistant,
        user_message=user_message,
        requested_logical_model=requested_model,
        model_preset_override=model_preset,
    )
    t_stage = _log_timing("7_build_payload", t_stage, request_id, f"messages_count={len(payload.get('messages', []))}")

    # Read path: best-effort memory retrieval (default-not-retrieve, gated).
    try:
        auth_key = _to_authenticated_api_key(api_key=ctx.api_key, current_user=current_user)
        mem_ctx = await maybe_retrieve_user_memory_context(
            db,
            redis=redis,
            client=client,
            api_key=auth_key,
            effective_provider_ids=effective_provider_ids,
            owner_user_id=UUID(str(current_user.id)),
            project_id=UUID(str(ctx.project_id)),
            user_text=(content or ""),
            summary_text=getattr(conv, "summary_text", None),
            top_k=3,
            idempotency_key=f"mem_read:{conv.id}:{user_message.id}",
        )
        if mem_ctx:
            payload["messages"] = inject_memory_context_into_messages(
                list(payload.get("messages", []) or []),
                memory_context=mem_ctx,
            )
    except Exception:  # pragma: no cover - best-effort only
        pass

    t_bridge_start = time.perf_counter()
    payload, effective_bridge_agent_ids, _tool_filters, openai_tools, tool_name_map = await _load_bridge_tools_for_payload(
        base_payload=payload,
        bridge_agent_id=bridge_agent_id,
        bridge_agent_ids=bridge_agent_ids,
        bridge_tool_selections=bridge_tool_selections,
    )
    t_stage = _log_timing("8_load_bridge_tools", t_bridge_start, request_id, f"agents={len(effective_bridge_agent_ids)} tools={len(openai_tools)}")

    run = create_run_record(
        db,
        user_id=UUID(str(current_user.id)),
        api_key_id=ctx.project_id,
        message_id=UUID(str(user_message.id)),
        requested_logical_model=requested_model,
        request_payload=payload,
    )
    t_stage = _log_timing("9_create_run_record", t_stage, request_id)

    # 记录准备阶段总耗时
    prep_ms = (time.perf_counter() - t_total_start) * 1000
    logger.info("[CHAT_TIMING] %s | PREP_COMPLETE | %.2fms | ready_to_stream", request_id, prep_ms)

    _append_run_event_best_effort(
        db,
        redis=redis,
        run_id=UUID(str(run.id)),
        event_type="message.created",
        payload={
            "type": "message.created",
            "conversation_id": str(conv.id),
            "user_message_id": str(user_message.id),
            "assistant_message_id": str(assistant_message.id),
            "baseline_run": _run_to_summary(run),
        },
    )
    yield _encode_sse_event(
        event_type="message.created",
        data={
            "type": "message.created",
            "conversation_id": str(conv.id),
            "user_message_id": str(user_message.id),
            "assistant_message_id": str(assistant_message.id),
            "baseline_run": _run_to_summary(run),
        },
    )

    auth_key = _to_authenticated_api_key(api_key=ctx.api_key, current_user=current_user)
    parts: list[str] = []
    errored = False
    t_stream_start = time.perf_counter()
    first_chunk_received = False
    tool_loop_enabled = bool(effective_bridge_agent_ids and openai_tools)
    stream_filter = _ToolTagStreamFilter(holdback_chars=64) if tool_loop_enabled else None

    async for item in execute_run_stream(
        db,
        redis=redis,
        client=client,
        api_key=auth_key,
        effective_provider_ids=effective_provider_ids,
        conversation=conv,
        assistant=assistant,
        user_message=user_message,
        run=run,
        requested_logical_model=requested_model,
        payload_override=payload,
    ):
        if not isinstance(item, dict):
            continue
        itype = str(item.get("type") or "")

        if itype == "run.delta":
            delta = item.get("delta")
            if isinstance(delta, str) and delta:
                emit_delta = delta
                if stream_filter is not None:
                    emit_delta = stream_filter.feed(delta)
                # Strip thinking blocks from streaming deltas
                if emit_delta:
                    emit_delta = _strip_think_blocks(emit_delta)
                if not first_chunk_received:
                    first_chunk_received = True
                    _log_timing("10_first_chunk_received", t_stream_start, request_id)
                if emit_delta:
                    parts.append(emit_delta)
                    yield _encode_sse_event(
                        event_type="message.delta",
                        data={
                            "type": "message.delta",
                            "conversation_id": str(conv.id),
                            "assistant_message_id": str(assistant_message.id),
                            "run_id": str(run.id),
                            "delta": emit_delta,
                        },
                    )
        elif itype == "run.error":
            errored = True
            yield _encode_sse_event(
                event_type="message.error",
                data={
                    "type": "message.error",
                    "conversation_id": str(conv.id),
                    "assistant_message_id": str(assistant_message.id),
                    "run_id": str(run.id),
                    "error_code": item.get("error_code"),
                    "error": item.get("error"),
                },
            )
            break

    if stream_filter is not None:
        tail = stream_filter.flush()
        if tail:
            # Strip thinking blocks from flushed tail
            tail = _strip_think_blocks(tail)
        if tail:
            parts.append(tail)
            yield _encode_sse_event(
                event_type="message.delta",
                data={
                    "type": "message.delta",
                    "conversation_id": str(conv.id),
                    "assistant_message_id": str(assistant_message.id),
                    "run_id": str(run.id),
                    "delta": tail,
                },
            )

    t_stage = _log_timing("11_stream_complete", t_stream_start, request_id, f"chunks={len(parts)} errored={errored}")
    run = refresh_run(db, run)

    # Tool-calling loop（流式结束后补充执行）
    if run.status == "succeeded" and effective_bridge_agent_ids and openai_tools:
        t_tool_loop_start = time.perf_counter()
        tool_loop_provider_ids = effective_provider_ids
        pinned_provider_id = str(getattr(run, "selected_provider_id", None) or "").strip()
        if pinned_provider_id and pinned_provider_id in tool_loop_provider_ids:
            tool_loop_provider_ids = {pinned_provider_id}

        runner = _create_standard_tool_loop_runner(
            db=db,
            redis=redis,
            client=client,
            auth_key=auth_key,
            effective_provider_ids=tool_loop_provider_ids,
            conversation_id=str(conv.id),
            assistant_id=UUID(str(getattr(assistant, "id", None))) if getattr(assistant, "id", None) else None,
            requested_model=requested_model,
            run_id=UUID(str(run.id)),
        )

        result = await runner.run(
            conversation_id=str(conv.id),
            run_id=str(run.id),
            base_payload=payload,
            first_response_payload=getattr(run, "response_payload", None),
            effective_bridge_agent_ids=effective_bridge_agent_ids,
            tool_name_map=tool_name_map,
            assistant_message_id=str(assistant_message.id),
            user_message_id=str(user_message.id),
            idempotency_prefix=f"chat:{run.id}:tool_loop",
        )

        _log_timing(
            "11_tool_loop",
            t_tool_loop_start,
            request_id,
            f"did_run={result.did_run} invocations={len(result.tool_invocations)} error={result.error_code or ''}",
        )

        if result.did_run:
            delta_text = result.output_text
            if result.error_code:
                run.status = "failed"
                run.error_code = result.error_code
                run.error_message = result.error_message
                delta_text = None
            elif delta_text and delta_text.strip():
                run.output_text = delta_text
                run.output_preview = delta_text.strip()[:380].rstrip()
            else:
                run.status = "failed"
                run.error_code = "TOOL_LOOP_FAILED"
                run.error_message = "tool loop finished without assistant content"
                delta_text = None

            run.response_payload = {
                "bridge": {
                    "agent_ids": effective_bridge_agent_ids,
                    "tool_invocations": result.tool_invocations,
                },
                "first_response": result.first_response_payload,
                "final_response": result.final_response_payload,
            }
            run = persist_run(db, run)

            if delta_text:
                parts = []
                for chunk in split_text_into_deltas(delta_text):
                    parts.append(chunk)
                    yield _encode_sse_event(
                        event_type="message.delta",
                        data={
                            "type": "message.delta",
                            "conversation_id": str(conv.id),
                            "assistant_message_id": str(assistant_message.id),
                            "run_id": str(run.id),
                            "delta": chunk,
                        },
                    )

    if not errored and run.status == "succeeded" and run.output_text:
        finalize_assistant_message_after_user_sequence(
            db,
            conversation_id=UUID(str(conv.id)),
            user_sequence=int(user_message.sequence or 0),
            content_text=run.output_text,
        )
        try:
            await maybe_update_conversation_summary(
                db,
                redis=redis,
                client=client,
                api_key=auth_key,
                effective_provider_ids=effective_provider_ids,
                conversation_id=UUID(str(conv.id)),
                assistant_id=UUID(str(getattr(assistant, "id", None))) if getattr(assistant, "id", None) else None,
                requested_logical_model=requested_model,
                new_until_sequence=int(user_message.sequence or 0) + 1,
            )
        except Exception:  # pragma: no cover - best-effort only
            logger.debug(
                "chat_app: conversation summary update failed (conversation_id=%s)",
                str(conv.id),
                exc_info=True,
            )

    # Auto-title conversation（异步入队，避免阻塞流式尾部）
    t_title_start = time.perf_counter()
    try:
        if int(user_message.sequence or 0) == 1 and not (getattr(conv, "title", None) or "").strip():
            _enqueue_auto_title_task(
                conversation_id=UUID(str(conv.id)),
                message_id=UUID(str(user_message.id)),
                user_id=UUID(str(current_user.id)),
                assistant_id=UUID(str(assistant.id)),
                requested_model_for_title_fallback=requested_model,
            )
            _log_timing("12_auto_title_enqueued", t_title_start, request_id)
    except Exception:  # pragma: no cover - best-effort only
        pass

    # === 性能计时结束 ===
    total_ms = (time.perf_counter() - t_total_start) * 1000
    logger.info("[CHAT_TIMING] %s | TOTAL | %.2fms | model=%s provider=%s status=%s chunks=%d",
                request_id, total_ms, requested_model, run.selected_provider_id, run.status, len(parts))

    _append_run_event_best_effort(
        db,
        redis=redis,
        run_id=UUID(str(run.id)),
        event_type="message.completed" if run.status == "succeeded" else "message.failed",
        payload={
            "type": "message.completed" if run.status == "succeeded" else "message.failed",
            "conversation_id": str(conv.id),
            "assistant_message_id": str(assistant_message.id),
            "baseline_run": _run_to_summary(run),
            "output_text": "".join(parts) if parts else None,
        },
    )
    yield _encode_sse_event(
        event_type="message.completed" if run.status == "succeeded" else "message.failed",
        data={
            "type": "message.completed" if run.status == "succeeded" else "message.failed",
            "conversation_id": str(conv.id),
            "assistant_message_id": str(assistant_message.id),
            "baseline_run": _run_to_summary(run),
            "output_text": "".join(parts) if parts else None,
        },
    )
    yield _encode_sse_event(event_type="done", data="[DONE]")


__all__ = ["send_message_and_run_baseline", "stream_message_and_run_baseline", "regenerate_assistant_message"]


async def regenerate_assistant_message(
    db: Session,
    *,
    redis: Redis,
    client: Any,
    current_user: AuthenticatedUser,
    assistant_message_id: UUID,
    override_logical_model: str | None = None,
    model_preset: dict | None = None,
    bridge_agent_id: str | None = None,
    bridge_agent_ids: list[str] | None = None,
    bridge_tool_selections: list[dict] | None = None,
) -> tuple[UUID, UUID]:
    """
    基于已有的 user 消息重新生成 assistant 回复：
    - 删除原有 assistant 消息（避免重复显示）
    - 重新执行 baseline run，生成新的 assistant 消息
    """
    assistant_msg = get_assistant_message(db, assistant_message_id)
    if assistant_msg is None or str(assistant_msg.role or "") != "assistant":
        raise bad_request("只支持对助手消息重试", details={"message_id": str(assistant_message_id)})

    conv = get_conversation(db, conversation_id=UUID(str(assistant_msg.conversation_id)), user_id=UUID(str(current_user.id)))

    user_msg = get_previous_user_message(db, assistant_msg)
    if user_msg is None:
        raise bad_request("未找到对应的用户消息，无法重试", details={"assistant_message_id": str(assistant_message_id)})

    user_text = ""
    if isinstance(user_msg.content, dict):
        user_text = str(user_msg.content.get("text") or "")
    if not user_text.strip():
        raise bad_request("用户消息内容为空，无法重试", details={"assistant_message_id": str(assistant_message_id)})

    # 删除原 assistant 消息，避免历史残留
    delete_message(db, assistant_msg)

    ctx = resolve_project_context(db, project_id=UUID(str(conv.api_key_id)), current_user=current_user)

    try:
        ensure_account_usable(db, user_id=UUID(str(current_user.id)))
    except InsufficientCreditsError as exc:
        raise bad_request(
            "积分不足",
            details={"code": "CREDIT_NOT_ENOUGH", "balance": exc.balance},
        )

    assistant = get_assistant(db, assistant_id=UUID(str(conv.assistant_id)), user_id=UUID(str(current_user.id)))

    # 复用上一条 run 的模型，否则按默认/项目回退
    last_run = get_last_run_for_message(db, user_msg.id)
    requested_model = override_logical_model or (last_run.requested_logical_model if last_run else assistant.default_logical_model)
    
    requested_model = await _resolve_final_model(
        db=db,
        redis=redis,
        client=client,
        current_user=current_user,
        ctx=ctx,
        assistant=assistant,
        requested_model=requested_model,
        user_text=user_text,
        model_preset=model_preset,
    )

    payload = build_openai_request_payload(
        db,
        conversation=conv,
        assistant=assistant,
        user_message=user_msg,
        requested_logical_model=requested_model,
        model_preset_override=model_preset,
    )

    effective_provider_ids = get_effective_provider_ids_for_user(
        db,
        user_id=UUID(str(current_user.id)),
        api_key=ctx.api_key,
        provider_scopes=list(
            getattr(get_or_default_project_eval_config(db, project_id=ctx.project_id), "provider_scopes", None)
            or DEFAULT_PROVIDER_SCOPES
        ),
    )

    # Read path: best-effort memory retrieval (default-not-retrieve, gated).
    try:
        auth_key = _to_authenticated_api_key(api_key=ctx.api_key, current_user=current_user)
        mem_ctx = await maybe_retrieve_user_memory_context(
            db,
            redis=redis,
            client=client,
            api_key=auth_key,
            effective_provider_ids=effective_provider_ids,
            owner_user_id=UUID(str(current_user.id)),
            project_id=UUID(str(ctx.project_id)),
            user_text=user_text,
            summary_text=getattr(conv, "summary_text", None),
            top_k=3,
            idempotency_key=f"mem_read:{conv.id}:{user_msg.id}",
        )
        if mem_ctx:
            payload["messages"] = inject_memory_context_into_messages(
                list(payload.get("messages", []) or []),
                memory_context=mem_ctx,
            )
    except Exception:  # pragma: no cover - best-effort only
        pass

    payload, effective_bridge_agent_ids, _tool_filters, openai_tools, tool_name_map = await _load_bridge_tools_for_payload(
        base_payload=payload,
        bridge_agent_id=bridge_agent_id,
        bridge_agent_ids=bridge_agent_ids,
        bridge_tool_selections=bridge_tool_selections,
    )

    run = create_run_record(
        db,
        user_id=UUID(str(current_user.id)),
        api_key_id=ctx.project_id,
        message_id=UUID(str(user_msg.id)),
        requested_logical_model=requested_model,
        request_payload=payload,
    )

    auth_key = _to_authenticated_api_key(api_key=ctx.api_key, current_user=current_user)
    run = await execute_run_non_stream(
        db,
        redis=redis,
        client=client,
        api_key=auth_key,
        effective_provider_ids=effective_provider_ids,
        conversation=conv,
        assistant=assistant,
        user_message=user_msg,
        run=run,
        requested_logical_model=requested_model,
        model_preset_override=model_preset,
        payload_override=payload,
    )

    if run.status == "succeeded" and effective_bridge_agent_ids and openai_tools:
        tool_loop_provider_ids = effective_provider_ids
        pinned_provider_id = str(getattr(run, "selected_provider_id", None) or "").strip()
        if pinned_provider_id and pinned_provider_id in tool_loop_provider_ids:
            tool_loop_provider_ids = {pinned_provider_id}

        runner = _create_standard_tool_loop_runner(
            db=db,
            redis=redis,
            client=client,
            auth_key=auth_key,
            effective_provider_ids=tool_loop_provider_ids,
            conversation_id=str(conv.id),
            assistant_id=UUID(str(getattr(assistant, "id", None))) if getattr(assistant, "id", None) else None,
            requested_model=requested_model,
            run_id=UUID(str(run.id)),
        )

        result = await runner.run(
            conversation_id=str(conv.id),
            run_id=str(run.id),
            base_payload=payload,
            first_response_payload=getattr(run, "response_payload", None),
            effective_bridge_agent_ids=effective_bridge_agent_ids,
            tool_name_map=tool_name_map,
            idempotency_prefix=f"chat:{run.id}:tool_loop",
        )

        if result.did_run:
            output_text = result.output_text
            if result.error_code:
                run.status = "failed"
                run.error_code = result.error_code
                run.error_message = result.error_message
            elif output_text and output_text.strip():
                run.output_text = output_text
                run.output_preview = output_text.strip()[:380].rstrip()
            else:
                run.status = "failed"
                run.error_code = "TOOL_LOOP_FAILED"
                run.error_message = "tool loop finished without assistant content"

            run.response_payload = {
                "bridge": {
                    "agent_ids": effective_bridge_agent_ids,
                    "tool_invocations": result.tool_invocations,
                },
                "first_response": result.first_response_payload,
                "final_response": result.final_response_payload,
            }
            run = persist_run(db, run)

    assistant_msg_new: Message | None = None
    if run.status == "succeeded" and run.output_text:
        assistant_msg_new = create_assistant_message_after_user(
            db,
            conversation_id=UUID(str(conv.id)),
            user_sequence=int(user_msg.sequence or 0),
            content_text=run.output_text,
        )
        try:
            await maybe_update_conversation_summary(
                db,
                redis=redis,
                client=client,
                api_key=auth_key,
                effective_provider_ids=effective_provider_ids,
                conversation_id=UUID(str(conv.id)),
                assistant_id=UUID(str(getattr(assistant, "id", None))) if getattr(assistant, "id", None) else None,
                requested_logical_model=requested_model,
                new_until_sequence=int(getattr(assistant_msg_new, "sequence", 0) or 0),
            )
        except Exception:  # pragma: no cover - best-effort only
            logger.debug(
                "chat_app: conversation summary update failed (conversation_id=%s)",
                str(conv.id),
                exc_info=True,
            )

    # 首问自动标题（保持行为一致）
    try:
        if int(user_msg.sequence or 0) == 1 and not (conv.title or "").strip():
            await _maybe_auto_title_conversation(
                db,
                redis=redis,
                client=client,
                current_user=current_user,
                conv=conv,
                assistant=assistant,
                effective_provider_ids=effective_provider_ids,
                user_text=user_text,
                user_sequence=int(user_msg.sequence or 0),
                requested_model_for_title_fallback=requested_model,
            )
    except Exception:  # pragma: no cover
        pass

    if assistant_msg_new is None:
        raise bad_request("生成失败", details={"run_status": run.status, "error_code": run.error_code})

    return UUID(str(assistant_msg_new.id)), UUID(str(run.id))
