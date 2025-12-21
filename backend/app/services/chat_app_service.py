from __future__ import annotations

import json
import uuid
from collections.abc import AsyncIterator
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.services.bridge_gateway_client import BridgeGatewayClient
from app.services.bridge_tool_runner import (
    BridgeToolInvocation,
    bridge_tools_by_agent_to_openai_tools,
    extract_openai_tool_calls,
    invoke_bridge_tool_and_wait,
    tool_call_to_args,
)

try:
    from redis.asyncio import Redis
except ModuleNotFoundError:  # pragma: no cover
    Redis = object  # type: ignore

from app.api.v1.chat.provider_selector import ProviderSelector
from app.api.v1.chat.request_handler import RequestHandler
from app.auth import AuthenticatedAPIKey
from app.errors import bad_request
from app.jwt_auth import AuthenticatedUser
from app.models import APIKey
from app.services.bandit_policy_service import recommend_challengers
from app.services.chat_history_service import (
    create_assistant_message_after_user,
    create_assistant_message_placeholder_after_user,
    create_user_message,
    finalize_assistant_message_after_user_sequence,
    get_assistant,
    get_conversation,
)
from app.services.chat_run_service import build_openai_request_payload, create_run_record, execute_run_non_stream
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

def _sanitize_conversation_title(value: str) -> str:
    title = (value or "").strip()
    if not title:
        return ""

    # Remove common wrapping quotes
    if len(title) >= 2 and title[0] == title[-1] and title[0] in {"'", '"', "“", "”", "‘", "’", "《", "》"}:
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


def _truncate_title_input(value: str, *, max_len: int = 1000) -> str:
    text = (value or "").strip()
    if not text:
        return ""
    if len(text) <= max_len:
        return text
    return text[:max_len].rstrip()


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

    conv.title = title
    db.add(conv)
    db.commit()
    db.refresh(conv)


async def send_message_and_run_baseline(
    db: Session,
    *,
    redis: Redis,
    client: Any,
    current_user: AuthenticatedUser,
    conversation_id: UUID,
    content: str,
    override_logical_model: str | None = None,
    model_preset: dict | None = None,
    bridge_agent_id: str | None = None,
    bridge_agent_ids: list[str] | None = None,
) -> tuple[UUID, UUID]:
    """
    创建 user message 并同步执行 baseline run，随后写入 assistant message（用于历史上下文）。

    Returns:
        (message_id, baseline_run_id)
    """
    conv = get_conversation(db, conversation_id=conversation_id, user_id=UUID(str(current_user.id)))
    ctx = resolve_project_context(db, project_id=UUID(str(conv.api_key_id)), current_user=current_user)

    # 余额校验（沿用网关规则）
    try:
        ensure_account_usable(db, user_id=UUID(str(current_user.id)))
    except InsufficientCreditsError as exc:
        raise bad_request(
            "积分不足",
            details={"code": "CREDIT_NOT_ENOUGH", "balance": exc.balance},
        )

    assistant = get_assistant(db, assistant_id=UUID(str(conv.assistant_id)), user_id=UUID(str(current_user.id)))
    requested_model = override_logical_model or assistant.default_logical_model
    if requested_model == PROJECT_INHERIT_SENTINEL:
        requested_model = (getattr(ctx.api_key, "chat_default_logical_model", None) or "").strip() or DEFAULT_PROJECT_CHAT_MODEL
    if not requested_model:
        raise bad_request("未指定模型")

    cfg = get_or_default_project_eval_config(db, project_id=ctx.project_id)

    effective_provider_ids = get_effective_provider_ids_for_user(
        db,
        user_id=UUID(str(current_user.id)),
        api_key=ctx.api_key,
        provider_scopes=list(getattr(cfg, "provider_scopes", None) or DEFAULT_PROVIDER_SCOPES),
    )

    if requested_model == "auto":
        candidates = list(cfg.candidate_logical_models or [])
        if not candidates:
            raise bad_request(
                "当前助手默认模型为 auto，但项目未配置 candidate_logical_models",
                details={"project_id": str(ctx.project_id)},
            )

        # 用 assistant preset（+override）构造一个“能力/预算判定用”的轻量 payload：
        # - 只需要 tools / max_tokens 等字段即可用于候选池过滤；
        # - messages 依赖实际历史上下文，这里不强依赖。
        preset_payload: dict[str, Any] = {}
        if isinstance(assistant.model_preset, dict):
            preset_payload.update(assistant.model_preset)
        if isinstance(model_preset, dict):
            preset_payload.update(model_preset)

        # 过滤不可用/无权限/故障的模型
        selector = ProviderSelector(client=client, redis=redis, db=db)
        candidates = await selector.check_candidate_availability(
            candidate_logical_models=candidates,
            effective_provider_ids=effective_provider_ids,
            api_style="openai",  # 默认聊天场景
            user_id=UUID(str(current_user.id)),
            is_superuser=current_user.is_superuser,
            request_payload=preset_payload or None,
            budget_credits=cfg.budget_per_eval_credits,
        )

        if not candidates:
             raise bad_request(
                "auto 模式下无可用的候选模型（均被禁用或无健康上游）",
                details={"project_id": str(ctx.project_id)},
            )

        rec = recommend_challengers(
            db,
            project_id=ctx.project_id,
            assistant_id=UUID(str(assistant.id)),
            baseline_logical_model="auto",
            user_text=content,
            context_features=build_rule_context_features(user_text=content, request_payload=None),
            candidate_logical_models=candidates,
            k=1,
            policy_version="ts-v1",
        )
        if not rec.candidates:
            raise bad_request(
                "auto 模式下无法选择候选模型",
                details={"project_id": str(ctx.project_id)},
            )
        requested_model = rec.candidates[0].logical_model

    user_message = create_user_message(db, conversation=conv, content_text=content)
    payload = build_openai_request_payload(
        db,
        conversation=conv,
        assistant=assistant,
        user_message=user_message,
        requested_logical_model=requested_model,
        model_preset_override=model_preset,
    )

    bridge_tools_by_agent: dict[str, list[dict[str, Any]]] = {}
    openai_tools: list[dict[str, Any]] = []
    tool_name_map: dict[str, tuple[str, str]] = {}  # openai_tool_name -> (agent_id, bridge_tool_name)

    # bridge_agent_ids takes precedence; bridge_agent_id is legacy.
    effective_bridge_agent_ids: list[str] = []
    if isinstance(bridge_agent_ids, list) and bridge_agent_ids:
        effective_bridge_agent_ids = [str(x).strip() for x in bridge_agent_ids if str(x).strip()]
    elif (bridge_agent_id or "").strip():
        effective_bridge_agent_ids = [str(bridge_agent_id).strip()]

    # Hard cap to prevent oversized tool injection.
    if len(effective_bridge_agent_ids) > 5:
        effective_bridge_agent_ids = effective_bridge_agent_ids[:5]

    if effective_bridge_agent_ids:
        try:
            bridge = BridgeGatewayClient()
            for aid in effective_bridge_agent_ids:
                try:
                    tools_resp = await bridge.list_tools(aid)
                except Exception:
                    continue
                if isinstance(tools_resp, dict) and isinstance(tools_resp.get("tools"), list):
                    bridge_tools_by_agent[aid] = [t for t in tools_resp["tools"] if isinstance(t, dict)]

            openai_tools, tool_name_map = bridge_tools_by_agent_to_openai_tools(
                bridge_tools_by_agent=bridge_tools_by_agent,
            )
            if openai_tools:
                payload = dict(payload)
                payload["tools"] = openai_tools
                payload["tool_choice"] = "auto"
        except Exception:
            # Best-effort: do not block baseline chat if bridge tools cannot be loaded.
            openai_tools = []

    run = create_run_record(
        db,
        user_id=UUID(str(current_user.id)),
        api_key_id=ctx.project_id,
        message_id=UUID(str(user_message.id)),
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
        user_message=user_message,
        run=run,
        requested_logical_model=requested_model,
        model_preset_override=model_preset,
        payload_override=payload,
    )

    # Tool-calling loop (best-effort; only when bridge_agent_ids is provided).
    if run.status == "succeeded" and effective_bridge_agent_ids and openai_tools:
        tool_calls = extract_openai_tool_calls(run.response_payload)
        if tool_calls:
            invocations: list[BridgeToolInvocation] = []
            tool_messages: list[dict[str, Any]] = []
            for tc in tool_calls:
                tool_name, args, tool_call_id = tool_call_to_args(tc)
                if not tool_name:
                    continue
                mapped = tool_name_map.get(tool_name)
                if mapped:
                    target_agent_id, target_tool_name = mapped
                else:
                    # Backward compatibility: when only one agent is selected, allow direct tool name.
                    target_agent_id = effective_bridge_agent_ids[0]
                    target_tool_name = tool_name
                req_id = "req_" + uuid.uuid4().hex
                invocations.append(
                    BridgeToolInvocation(
                        req_id=req_id,
                        agent_id=target_agent_id,
                        tool_name=target_tool_name,
                        tool_call_id=tool_call_id,
                    )
                )
                tool_result = await invoke_bridge_tool_and_wait(
                    req_id=req_id,
                    agent_id=target_agent_id,
                    tool_name=target_tool_name,
                    arguments=args,
                    timeout_ms=60000,
                    result_timeout_seconds=120.0,
                )
                tool_messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tool_call_id or req_id,
                        "content": json.dumps(
                            {
                                "req_id": req_id,
                                "agent_id": target_agent_id,
                                "tool_name": target_tool_name,
                                "model_tool_name": tool_name,
                                "ok": tool_result.ok,
                                "exit_code": tool_result.exit_code,
                                "canceled": tool_result.canceled,
                                "result_json": tool_result.result_json,
                                "error": tool_result.error,
                            },
                            ensure_ascii=False,
                        ),
                    }
                )

            if invocations and tool_messages:
                # Follow-up call: append assistant tool_calls message and tool outputs.
                follow_payload = dict(payload)
                follow_messages = list(payload.get("messages") or [])
                follow_messages.append({"role": "assistant", "content": None, "tool_calls": tool_calls})
                follow_messages.extend(tool_messages)
                follow_payload["messages"] = follow_messages
                follow_payload["tool_choice"] = "none"

                handler = RequestHandler(api_key=auth_key, db=db, redis=redis, client=client)
                resp = await handler.handle(
                    payload=follow_payload,
                    requested_model=requested_model,
                    lookup_model_id=requested_model,
                    api_style="openai",
                    effective_provider_ids=effective_provider_ids,
                    session_id=str(conv.id),
                    assistant_id=UUID(str(getattr(assistant, "id", None))) if getattr(assistant, "id", None) else None,
                    billing_reason="chat_tool_loop",
                    idempotency_key=f"chat:{run.id}:tool_loop",
                )

                follow_response_payload: dict[str, Any] | None = None
                try:
                    raw = resp.body.decode("utf-8", errors="ignore")
                    parsed = json.loads(raw)
                    if isinstance(parsed, dict):
                        follow_response_payload = parsed
                except Exception:
                    follow_response_payload = None

                output_text = _extract_first_choice_text(follow_response_payload)
                if output_text and output_text.strip():
                    run.output_text = output_text
                    run.output_preview = output_text.strip()[:380].rstrip()
                else:
                    run.status = "failed"
                    run.error_code = "TOOL_LOOP_FAILED"
                    run.error_message = "tool loop finished without assistant content"

                run.response_payload = {
                    "bridge": {
                        "agent_ids": effective_bridge_agent_ids,
                        "tool_invocations": [
                            {
                                "req_id": it.req_id,
                                "agent_id": it.agent_id,
                                "tool_name": it.tool_name,
                                "tool_call_id": it.tool_call_id,
                            }
                            for it in invocations
                        ],
                    },
                    "first_response": run.response_payload,
                    "final_response": follow_response_payload,
                }
                db.add(run)
                db.commit()
                db.refresh(run)

    # baseline 成功时写入 assistant message，作为后续上下文
    if run.status == "succeeded" and run.output_text:
        create_assistant_message_after_user(
            db,
            conversation_id=UUID(str(conv.id)),
            user_sequence=int(user_message.sequence or 0),
            content_text=run.output_text,
        )

    # Auto-title conversation based on the first user question (best-effort)
    try:
        if int(user_message.sequence or 0) == 1 and not (conv.title or "").strip():
            await _maybe_auto_title_conversation(
                db,
                redis=redis,
                client=client,
                current_user=current_user,
                conv=conv,
                assistant=assistant,
                effective_provider_ids=effective_provider_ids,
                user_text=content,
                user_sequence=int(user_message.sequence or 0),
                requested_model_for_title_fallback=requested_model,
            )
    except Exception:  # pragma: no cover - best-effort only
        # Never break the main chat flow for title generation.
        pass

    return UUID(str(user_message.id)), UUID(str(run.id))


async def stream_message_and_run_baseline(
    db: Session,
    *,
    redis: Redis,
    client: Any,
    current_user: AuthenticatedUser,
    conversation_id: UUID,
    content: str,
    override_logical_model: str | None = None,
    model_preset: dict | None = None,
) -> AsyncIterator[bytes]:
    """
    创建 user message 并以 SSE 流式执行 baseline run。

    注意：当前流式模式不支持 bridge 工具调用（tool loop）。
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
    if requested_model == PROJECT_INHERIT_SENTINEL:
        requested_model = (getattr(ctx.api_key, "chat_default_logical_model", None) or "").strip() or DEFAULT_PROJECT_CHAT_MODEL
    if not requested_model:
        raise bad_request("未指定模型")

    cfg = get_or_default_project_eval_config(db, project_id=ctx.project_id)
    effective_provider_ids = get_effective_provider_ids_for_user(
        db,
        user_id=UUID(str(current_user.id)),
        api_key=ctx.api_key,
        provider_scopes=list(getattr(cfg, "provider_scopes", None) or DEFAULT_PROVIDER_SCOPES),
    )

    if requested_model == "auto":
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

        selector = ProviderSelector(client=client, redis=redis, db=db)
        candidates = await selector.check_candidate_availability(
            candidate_logical_models=candidates,
            effective_provider_ids=effective_provider_ids,
            api_style="openai",
            user_id=UUID(str(current_user.id)),
            is_superuser=current_user.is_superuser,
            request_payload=preset_payload or None,
            budget_credits=cfg.budget_per_eval_credits,
        )

        if not candidates:
            raise bad_request(
                "auto 模式下无可用的候选模型（均被禁用或无健康上游）",
                details={"project_id": str(ctx.project_id)},
            )

        rec = recommend_challengers(
            db,
            project_id=ctx.project_id,
            assistant_id=UUID(str(assistant.id)),
            baseline_logical_model="auto",
            user_text=content,
            context_features=build_rule_context_features(user_text=content, request_payload=None),
            candidate_logical_models=candidates,
            k=1,
            policy_version="ts-v1",
        )
        if not rec.candidates:
            raise bad_request(
                "auto 模式下无法选择候选模型",
                details={"project_id": str(ctx.project_id)},
            )
        requested_model = rec.candidates[0].logical_model

    user_message = create_user_message(db, conversation=conv, content_text=content)
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

    run = create_run_record(
        db,
        user_id=UUID(str(current_user.id)),
        api_key_id=ctx.project_id,
        message_id=UUID(str(user_message.id)),
        requested_logical_model=requested_model,
        request_payload=payload,
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
                parts.append(delta)
                yield _encode_sse_event(
                    event_type="message.delta",
                    data={
                        "type": "message.delta",
                        "conversation_id": str(conv.id),
                        "assistant_message_id": str(assistant_message.id),
                        "run_id": str(run.id),
                        "delta": delta,
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

    db.refresh(run)
    if not errored and run.status == "succeeded" and run.output_text:
        finalize_assistant_message_after_user_sequence(
            db,
            conversation_id=UUID(str(conv.id)),
            user_sequence=int(user_message.sequence or 0),
            content_text=run.output_text,
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


__all__ = ["send_message_and_run_baseline", "stream_message_and_run_baseline"]
