from __future__ import annotations

import datetime as dt
import json
import time
from dataclasses import dataclass
from typing import Any, Literal
from uuid import UUID

from sqlalchemy.orm import Session as DbSession

try:
    from redis.asyncio import Redis
except ModuleNotFoundError:  # pragma: no cover
    Redis = object  # type: ignore[misc,assignment]

from app.api.v1.chat.request_handler import RequestHandler
from app.auth import AuthenticatedAPIKey
from app.services.kb_attribute_schema import filter_structured_ops, get_allowed_keys_description
from app.services.memory_metrics_buffer import get_memory_metrics_recorder
from app.utils.response_utils import extract_first_choice_text, parse_json_response_body

MemoryScope = Literal["none", "user", "system"]
StructuredScope = Literal["user", "project"]


@dataclass(frozen=True)
class MemoryRouteDecision:
    should_store: bool
    scope: MemoryScope
    memory_text: str
    memory_items: list[dict[str, Any]]
    structured_ops: list[dict[str, Any]]


_SYSTEM_PROMPT = (
    "Role: 你是一个 AI 记忆网关的“决策与提取引擎”（相当于海马体）。\n"
    "你将分析一段最近的对话，决定哪些信息值得长期存储，并完成“清洗改写 + 归类 + 维度路由”。\n"
    "\n"
    "目标：\n"
    "1) 决策：是否需要写入长期记忆（should_store）。\n"
    "2) 路由：若写入，写到 user 维度还是 system 维度（scope）。\n"
    "3) 清洗：把口语/上下文依赖的表达改写为独立、去上下文的陈述句（atomic）。\n"
    "4) 归类：为每条记忆标注 category 与 keywords（用于后续检索过滤）。\n"
    "\n"
    "记忆分类（category，仅用于元数据标注，不等同于 scope）：\n"
    "- user_profile：用户画像（职业/技能水平/长期状态/位置等稳定信息）。\n"
    "- preference：用户偏好（回复风格、工具偏好、语言习惯、格式要求、禁忌）。\n"
    "- project_context：项目/工作上下文（长期有效的项目约束、规范、默认设置）。\n"
    "- fact：用户明确要求记住、且短期不会变化的事实/笔记。\n"
    "\n"
    "决策规则（非常重要）：\n"
    "- Ignore：闲聊/客套、一次性临时问题、纯指令（“写个脚本”）、情绪发泄，不存。\n"
    "- Rewrite：若出现“它/那个/上次/这里”等指代，必须结合上下文替换成明确名词。\n"
    "- Atomicity：每条记忆必须独立完整，即使脱离上下文也能看懂。\n"
    "- Safety：严禁输出任何密钥/密码/token/API key/私钥/手机号/邮箱/地址等敏感信息；若对话包含敏感信息，也不要写入记忆。\n"
    "\n"
    "scope 选择规则：\n"
    "- user：用户个人事实/偏好/长期约束/待办/项目私有细节。\n"
    "- system：仅当内容“与任何特定用户无关、无隐私、可复用、通用”的结论/步骤/经验规则；如包含个人信息或项目专属细节，一律不要选 system。\n"
    "\n"
    "结构化属性（structured_ops，用于写入 PostgreSQL 形成确定性行为）：\n"
    "- 仅提取“明确、稳定、会影响后续行为”的偏好/约束（不要写临时状态）。\n"
    "- scope 只能是：user（用户偏好）或 project（项目约束）。\n"
    "- op 目前仅支持：UPSERT（同一个 subject + key 覆盖更新）。\n"
    "- 严禁写入任何密钥/密码/token/API key/私钥/手机号/邮箱/地址等敏感信息；如对话包含敏感信息，structured_ops 也必须为空。\n"
    "\n"
    "Key 白名单（严格限制，只允许使用以下 key）：\n"
    f"{get_allowed_keys_description()}\n"
    "\n"
    "输出格式：必须且只能输出 JSON（不要 Markdown、不要解释），字段如下：\n"
    "{\n"
    '  "should_store": true|false,\n'
    '  "scope": "none"|"user"|"system",\n'
    '  "memory_text": "string（把 memory_items[*].content 用 \\n 连接；若不存则为空字符串）",\n'
    '  "memory_items": [\n'
    "    {\n"
    '      "content": "独立陈述句",\n'
    '      "category": "user_profile|preference|project_context|fact",\n'
    '      "keywords": ["k1","k2"]\n'
    "    }\n"
    "  ]\n"
    '  ,"structured_ops": [\n'
    "    {\n"
    '      "op": "UPSERT",\n'
    '      "scope": "user|project",\n'
    '      "category": "preference|constraint",\n'
    '      "key": "string",\n'
    '      "value": "any json",\n'
    '      "confidence": 0.0,\n'
    '      "reason": "optional"\n'
    "    }\n"
    "  ]\n"
    "}\n"
    "当 should_store=false 时：scope=none，memory_text 为空字符串，memory_items 为空数组，structured_ops 为空数组。\n"
)


def _build_user_prompt(transcript: str) -> str:
    return (
        "请根据对话内容，输出符合 schema 的 JSON。\n"
        "注意：\n"
        "- 如果没有新记忆，请输出 should_store=false。\n"
        "- memory_items 只写“新出现的、长期有用”的信息，不要重复旧信息。\n"
        "- memory_text 必须等于把 memory_items 的 content 用换行符连接后的结果（便于后端直接 embedding）。\n"
        "\n"
        "对话内容（最近片段）：\n"
        f"{transcript}\n"
    )


def parse_memory_route_decision(text: str) -> MemoryRouteDecision:
    raw = (text or "").strip()
    if not raw:
        return MemoryRouteDecision(
            should_store=False, scope="none", memory_text="", memory_items=[], structured_ops=[]
        )

    try:
        obj = json.loads(raw)
    except Exception:
        # tolerate LLM extra whitespace/newlines, but do not attempt heuristic extraction
        return MemoryRouteDecision(
            should_store=False, scope="none", memory_text="", memory_items=[], structured_ops=[]
        )

    if not isinstance(obj, dict):
        return MemoryRouteDecision(
            should_store=False, scope="none", memory_text="", memory_items=[], structured_ops=[]
        )

    should_store = bool(obj.get("should_store", False))
    scope = str(obj.get("scope", "none") or "none").strip().lower()
    if scope not in ("none", "user", "system"):
        scope = "none"
    memory_text_raw = obj.get("memory_text")
    memory_text = memory_text_raw.strip() if isinstance(memory_text_raw, str) else ""

    memory_items_raw = obj.get("memory_items")
    memory_items: list[dict[str, Any]] = []
    if isinstance(memory_items_raw, list):
        for it in memory_items_raw:
            if not isinstance(it, dict):
                continue
            content = it.get("content")
            category = it.get("category")
            keywords = it.get("keywords")
            if not isinstance(content, str) or not content.strip():
                continue
            if not isinstance(category, str) or not category.strip():
                category = "fact"
            if not isinstance(keywords, list):
                keywords = []
            normalized_keywords: list[str] = []
            for kw in keywords:
                if isinstance(kw, str) and kw.strip():
                    normalized_keywords.append(kw.strip())
            memory_items.append(
                {
                    "content": content.strip(),
                    "category": category.strip(),
                    "keywords": normalized_keywords,
                }
            )

    if memory_items:
        joined = "\n".join([it["content"] for it in memory_items if isinstance(it.get("content"), str)]).strip()
        # Enforce consistency for downstream embedding.
        if joined:
            memory_text = joined

    structured_ops_raw = obj.get("structured_ops")
    structured_ops: list[dict[str, Any]] = []
    if isinstance(structured_ops_raw, list):
        for it in structured_ops_raw:
            if not isinstance(it, dict):
                continue
            op = str(it.get("op") or "").strip().upper()
            if op != "UPSERT":
                continue
            sscope = str(it.get("scope") or "").strip().lower()
            if sscope not in ("user", "project"):
                continue
            category = str(it.get("category") or "").strip().lower()
            if category not in ("preference", "constraint"):
                category = "preference" if sscope == "user" else "constraint"
            key = str(it.get("key") or "").strip()
            if not key:
                continue
            value = it.get("value")
            confidence = it.get("confidence")
            conf: float | None = None
            if isinstance(confidence, (int, float)):
                conf = float(confidence)
            reason = it.get("reason")
            structured_ops.append(
                {
                    "op": "UPSERT",
                    "scope": sscope,
                    "category": category,
                    "key": key,
                    "value": value,
                    "confidence": conf,
                    "reason": reason if isinstance(reason, str) else None,
                }
            )

    # Apply strict schema validation/filtering
    structured_ops = filter_structured_ops(structured_ops)

    if not should_store:
        return MemoryRouteDecision(
            should_store=False, scope="none", memory_text="", memory_items=[], structured_ops=structured_ops
        )
    if not memory_text:
        return MemoryRouteDecision(
            should_store=False, scope="none", memory_text="", memory_items=[], structured_ops=structured_ops
        )
    if scope == "none":
        return MemoryRouteDecision(
            should_store=False, scope="none", memory_text="", memory_items=[], structured_ops=structured_ops
        )

    return MemoryRouteDecision(
        should_store=True,
        scope=scope,  # type: ignore[arg-type]
        memory_text=memory_text,
        memory_items=memory_items,
        structured_ops=structured_ops,
    )


async def route_chat_memory(
    db: DbSession,
    *,
    redis: Redis,
    client: Any,
    api_key: AuthenticatedAPIKey,
    effective_provider_ids: set[str],
    router_logical_model: str,
    transcript: str,
    idempotency_key: str,
    user_id: UUID | None = None,
    project_id: UUID | None = None,
) -> MemoryRouteDecision:
    start_time = time.perf_counter()
    window_start = dt.datetime.now(dt.timezone.utc).replace(second=0, microsecond=0)
    recorder = get_memory_metrics_recorder()

    def _record_routing(decision: MemoryRouteDecision) -> None:
        latency_ms = (time.perf_counter() - start_time) * 1000
        recorder.record_routing(
            user_id=user_id,
            project_id=project_id,
            window_start=window_start,
            scope=decision.scope,
            latency_ms=latency_ms,
        )

    model = str(router_logical_model or "").strip()
    if not model:
        decision = MemoryRouteDecision(
            should_store=False, scope="none", memory_text="", memory_items=[], structured_ops=[]
        )
        _record_routing(decision)
        return decision

    text = (transcript or "").strip()
    if not text:
        decision = MemoryRouteDecision(
            should_store=False, scope="none", memory_text="", memory_items=[], structured_ops=[]
        )
        _record_routing(decision)
        return decision

    payload: dict[str, Any] = {
        "model": model,
        "messages": [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": _build_user_prompt(text)},
        ],
        "temperature": 0.0,
        "max_tokens": 256,
    }

    handler = RequestHandler(api_key=api_key, db=db, redis=redis, client=client)
    resp = await handler.handle(
        payload=payload,
        requested_model=model,
        lookup_model_id=model,
        api_style="openai",
        effective_provider_ids=effective_provider_ids,
        idempotency_key=idempotency_key,
        billing_reason="chat_memory_route",
    )
    response_payload = parse_json_response_body(resp)
    text_out = (extract_first_choice_text(response_payload) or "").strip()
    decision = parse_memory_route_decision(text_out)
    _record_routing(decision)
    return decision


async def route_chat_memory_with_raw(
    db: DbSession,
    *,
    redis: Redis,
    client: Any,
    api_key: AuthenticatedAPIKey,
    effective_provider_ids: set[str],
    router_logical_model: str,
    transcript: str,
    idempotency_key: str,
    user_id: UUID | None = None,
    project_id: UUID | None = None,
) -> tuple[MemoryRouteDecision, str]:
    start_time = time.perf_counter()
    window_start = dt.datetime.now(dt.timezone.utc).replace(second=0, microsecond=0)
    recorder = get_memory_metrics_recorder()

    def _record_routing(decision: MemoryRouteDecision) -> None:
        latency_ms = (time.perf_counter() - start_time) * 1000
        recorder.record_routing(
            user_id=user_id,
            project_id=project_id,
            window_start=window_start,
            scope=decision.scope,
            latency_ms=latency_ms,
        )

    model = str(router_logical_model or "").strip()
    if not model:
        decision = MemoryRouteDecision(
            should_store=False, scope="none", memory_text="", memory_items=[], structured_ops=[]
        )
        _record_routing(decision)
        return (decision, "")

    text = (transcript or "").strip()
    if not text:
        decision = MemoryRouteDecision(
            should_store=False, scope="none", memory_text="", memory_items=[], structured_ops=[]
        )
        _record_routing(decision)
        return (decision, "")

    payload: dict[str, Any] = {
        "model": model,
        "messages": [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": _build_user_prompt(text)},
        ],
        "temperature": 0.0,
        "max_tokens": 256,
    }

    handler = RequestHandler(api_key=api_key, db=db, redis=redis, client=client)
    resp = await handler.handle(
        payload=payload,
        requested_model=model,
        lookup_model_id=model,
        api_style="openai",
        effective_provider_ids=effective_provider_ids,
        idempotency_key=idempotency_key,
        billing_reason="chat_memory_route",
    )
    response_payload = parse_json_response_body(resp)
    raw_text = (extract_first_choice_text(response_payload) or "").strip()
    decision = parse_memory_route_decision(raw_text)
    _record_routing(decision)
    return decision, raw_text


__all__ = [
    "MemoryRouteDecision",
    "MemoryScope",
    "parse_memory_route_decision",
    "route_chat_memory",
    "route_chat_memory_with_raw",
]
