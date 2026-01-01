from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import Select, delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.errors import bad_request, forbidden, not_found
from app.models import AssistantPreset, Conversation, Message, Run
from app.services.api_key_service import get_api_key_by_id


def _parse_offset_cursor(cursor: str | None) -> int:
    if not cursor:
        return 0
    try:
        value = int(cursor)
    except (TypeError, ValueError):
        return 0
    return max(value, 0)


def _next_cursor(offset: int, limit: int, *, has_more: bool) -> str | None:
    if not has_more:
        return None
    return str(offset + limit)

def _ensure_project_accessible(db: Session, *, user_id: UUID, project_id: UUID) -> None:
    """
    MVP: project_id == api_key_id

    这里做一次显式校验，避免写入无效的 api_key_id：
    - 让前端/调用方在“选错 project_id”时得到清晰的 404
    - 避免后续在 run/eval 阶段才因为 resolve_project_context 失败而难以定位
    """
    api_key = get_api_key_by_id(db, project_id, user_id=user_id)
    if api_key is None:
        raise not_found("项目不存在或无权访问", details={"project_id": str(project_id)})


def create_assistant(
    db: Session,
    *,
    user_id: UUID,
    project_id: UUID | None,
    name: str,
    system_prompt: str,
    default_logical_model: str,
    model_preset: dict | None,
    title_logical_model: str | None = None,
) -> AssistantPreset:
    if project_id is not None:
        _ensure_project_accessible(db, user_id=user_id, project_id=project_id)

    assistant = AssistantPreset(
        user_id=user_id,
        api_key_id=project_id,
        name=name,
        system_prompt=system_prompt or "",
        default_logical_model=default_logical_model,
        title_logical_model=title_logical_model,
        model_preset=model_preset,
        archived_at=None,
    )
    db.add(assistant)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        # 这里原则上只会触发 uq_assistant_presets_user_project_name（避免把 FK/其他错误误报为“重名”）。
        raise bad_request("助手名称已存在")
    db.refresh(assistant)
    return assistant


def update_assistant(
    db: Session,
    *,
    assistant_id: UUID,
    user_id: UUID,
    name: str | None = None,
    system_prompt: str | None = None,
    default_logical_model: str | None = None,
    title_logical_model: str | None = None,
    title_logical_model_set: bool = False,
    model_preset: dict | None = None,
    archived: bool | None = None,
) -> AssistantPreset:
    assistant = db.execute(
        select(AssistantPreset).where(
            AssistantPreset.id == assistant_id,
            AssistantPreset.user_id == user_id,
        )
    ).scalars().first()
    if assistant is None:
        raise not_found("助手不存在", details={"assistant_id": str(assistant_id)})

    if name is not None:
        assistant.name = name
    if system_prompt is not None:
        assistant.system_prompt = system_prompt
    if default_logical_model is not None:
        assistant.default_logical_model = default_logical_model
    if title_logical_model_set:
        assistant.title_logical_model = title_logical_model
    if model_preset is not None:
        assistant.model_preset = model_preset
    if archived is not None:
        assistant.archived_at = datetime.now(UTC) if archived else None

    db.add(assistant)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise bad_request("助手名称已存在")
    db.refresh(assistant)
    return assistant


def list_assistants(
    db: Session,
    *,
    user_id: UUID,
    project_id: UUID | None = None,
    cursor: str | None = None,
    limit: int = 30,
) -> tuple[list[AssistantPreset], str | None]:
    offset = _parse_offset_cursor(cursor)
    limit = max(1, min(int(limit or 30), 100))

    stmt: Select[tuple[AssistantPreset]] = select(AssistantPreset).where(
        AssistantPreset.user_id == user_id,
        AssistantPreset.archived_at.is_(None),
    )
    if project_id is not None:
        stmt = stmt.where(AssistantPreset.api_key_id == project_id)
    stmt = stmt.order_by(AssistantPreset.updated_at.desc(), AssistantPreset.created_at.desc())
    rows = list(db.execute(stmt.offset(offset).limit(limit + 1)).scalars().all())
    has_more = len(rows) > limit
    items = rows[:limit]
    return items, _next_cursor(offset, limit, has_more=has_more)


def get_assistant(
    db: Session,
    *,
    assistant_id: UUID,
    user_id: UUID,
) -> AssistantPreset:
    assistant = db.execute(
        select(AssistantPreset).where(
            AssistantPreset.id == assistant_id,
            AssistantPreset.user_id == user_id,
        )
    ).scalars().first()
    if assistant is None:
        raise not_found("助手不存在", details={"assistant_id": str(assistant_id)})
    return assistant


def create_conversation(
    db: Session,
    *,
    user_id: UUID,
    project_id: UUID,
    assistant_id: UUID,
    title: str | None,
) -> Conversation:
    _ensure_project_accessible(db, user_id=user_id, project_id=project_id)
    assistant = get_assistant(db, assistant_id=assistant_id, user_id=user_id)
    if assistant.api_key_id is not None and UUID(str(assistant.api_key_id)) != project_id:
        raise forbidden("该助手不属于当前项目", details={"assistant_id": str(assistant_id), "project_id": str(project_id)})

    now = datetime.now(UTC)
    conv = Conversation(
        user_id=user_id,
        api_key_id=project_id,
        assistant_id=assistant_id,
        title=title,
        last_activity_at=now,
        archived_at=None,
    )
    db.add(conv)
    db.commit()
    db.refresh(conv)
    return conv


def list_conversations(
    db: Session,
    *,
    user_id: UUID,
    assistant_id: UUID,
    cursor: str | None = None,
    limit: int = 30,
    archived: bool = False,
) -> tuple[list[Conversation], str | None]:
    offset = _parse_offset_cursor(cursor)
    limit = max(1, min(int(limit or 30), 100))

    stmt: Select[tuple[Conversation]] = (
        select(Conversation)
        .where(
            Conversation.user_id == user_id,
            Conversation.assistant_id == assistant_id,
        )
    )
    if archived:
        stmt = stmt.where(Conversation.archived_at.is_not(None))
    else:
        stmt = stmt.where(Conversation.archived_at.is_(None))

    stmt = stmt.order_by(
        Conversation.is_pinned.desc(),
        Conversation.last_activity_at.desc(),
        Conversation.created_at.desc(),
    )

    rows = list(db.execute(stmt.offset(offset).limit(limit + 1)).scalars().all())
    has_more = len(rows) > limit
    items = rows[:limit]
    return items, _next_cursor(offset, limit, has_more=has_more)


def get_conversation(
    db: Session,
    *,
    conversation_id: UUID,
    user_id: UUID,
) -> Conversation:
    conv = db.execute(
        select(Conversation).where(
            Conversation.id == conversation_id,
            Conversation.user_id == user_id,
            Conversation.archived_at.is_(None),
        )
    ).scalars().first()
    if conv is None:
        raise not_found("会话不存在", details={"conversation_id": str(conversation_id)})
    return conv


def get_conversation_any(
    db: Session,
    *,
    conversation_id: UUID,
    user_id: UUID,
) -> Conversation:
    """
    允许读取已归档会话（用于查看历史消息）；写入类操作应继续使用 get_conversation（仅 active）。
    """
    conv = db.execute(
        select(Conversation).where(
            Conversation.id == conversation_id,
            Conversation.user_id == user_id,
        )
    ).scalars().first()
    if conv is None:
        raise not_found("会话不存在", details={"conversation_id": str(conversation_id)})
    return conv


def update_conversation(
    db: Session,
    *,
    conversation_id: UUID,
    user_id: UUID,
    title: str | None = None,
    archived: bool | None = None,
    is_pinned: bool | None = None,
    unread_count: int | None = None,
    summary_text: str | None = None,
    summary_text_set: bool = False,
) -> Conversation:
    conv = get_conversation_any(db, conversation_id=conversation_id, user_id=user_id)

    if title is not None:
        conv.title = title
    if archived is not None:
        conv.archived_at = datetime.now(UTC) if archived else None
    if is_pinned is not None:
        conv.is_pinned = is_pinned
    if unread_count is not None:
        conv.unread_count = unread_count
    if summary_text_set:
        text = (summary_text or "").strip()
        if not text:
            conv.summary_text = None
            conv.summary_until_sequence = 0
            conv.summary_updated_at = None
        else:
            last_seq = (
                db.execute(
                    select(func.max(Message.sequence)).where(Message.conversation_id == conversation_id)
                ).scalar()
                or 0
            )
            conv.summary_text = text
            conv.summary_until_sequence = int(last_seq or 0)
            conv.summary_updated_at = datetime.now(UTC)

    db.add(conv)
    db.commit()
    db.refresh(conv)
    return conv


def delete_conversation(
    db: Session,
    *,
    conversation_id: UUID,
    user_id: UUID,
) -> None:
    conv = get_conversation_any(db, conversation_id=conversation_id, user_id=user_id)
    db.delete(conv)
    db.commit()


def clear_conversation_messages(
    db: Session,
    *,
    conversation_id: UUID,
    user_id: UUID,
) -> Conversation:
    """
    清空会话内全部消息（并级联删除 runs/evals），保留会话本身。
    """
    conv = get_conversation_any(db, conversation_id=conversation_id, user_id=user_id)

    db.execute(delete(Message).where(Message.conversation_id == conversation_id))

    conv.last_message_content = None
    conv.unread_count = 0
    conv.last_activity_at = datetime.now(UTC)
    conv.summary_text = None
    conv.summary_until_sequence = 0
    conv.summary_updated_at = None

    db.add(conv)
    db.commit()
    db.refresh(conv)
    return conv


def delete_assistant(
    db: Session,
    *,
    assistant_id: UUID,
    user_id: UUID,
) -> None:
    assistant = db.execute(
        select(AssistantPreset).where(
            AssistantPreset.id == assistant_id,
            AssistantPreset.user_id == user_id,
        )
    ).scalars().first()
    if assistant is None:
        raise not_found("助手不存在", details={"assistant_id": str(assistant_id)})
    db.delete(assistant)
    db.commit()


def _next_message_sequence(db: Session, *, conversation_id: UUID) -> int:
    seq = db.execute(
        select(func.max(Message.sequence)).where(Message.conversation_id == conversation_id)
    ).scalar_one()
    if seq is None:
        return 1
    return int(seq) + 1


def create_user_message(
    db: Session,
    *,
    conversation: Conversation,
    content_text: str | None = None,
    input_audio: dict | None = None,
) -> Message:
    text = (content_text or "").strip()
    if not text and not isinstance(input_audio, dict):
        raise bad_request("消息内容不能为空")
    seq = _next_message_sequence(db, conversation_id=UUID(str(conversation.id)))
    content: dict = {"type": "text", "text": text}
    if isinstance(input_audio, dict) and input_audio:
        content["input_audio"] = dict(input_audio)
    msg = Message(
        conversation_id=conversation.id,
        role="user",
        content=content,
        sequence=seq,
    )
    conversation.last_activity_at = datetime.now(UTC)
    conversation.last_message_content = text or "（语音）"
    db.add_all([msg, conversation])
    db.commit()
    db.refresh(msg)
    return msg


def create_assistant_message_after_user(
    db: Session,
    *,
    conversation_id: UUID,
    user_sequence: int,
    content_text: str,
) -> Message:
    seq = int(user_sequence) + 1
    msg = Message(
        conversation_id=conversation_id,
        role="assistant",
        content={"type": "text", "text": content_text},
        sequence=seq,
    )
    db.add(msg)

    # Update conversation preview and unread count
    conv = db.get(Conversation, conversation_id)
    if conv:
        conv.last_message_content = content_text
        conv.unread_count += 1
        conv.last_activity_at = datetime.now(UTC)
        db.add(conv)

    db.commit()
    db.refresh(msg)
    return msg


def create_assistant_message_placeholder_after_user(
    db: Session,
    *,
    conversation_id: UUID,
    user_sequence: int,
) -> Message:
    """
    创建一个 assistant 占位消息（空文本），用于流式生成时“预占位”会话序列：
    - 避免用户在生成过程中再次发送消息导致 sequence 混乱；
    - 不更新 conversation 的 last_message_content / unread_count（等最终文本写入时再更新）。
    """
    seq = int(user_sequence) + 1
    msg = Message(
        conversation_id=conversation_id,
        role="assistant",
        content={"type": "text", "text": ""},
        sequence=seq,
    )
    db.add(msg)
    db.commit()
    db.refresh(msg)
    return msg


def create_assistant_image_generation_placeholder_after_user(
    db: Session,
    *,
    conversation_id: UUID,
    user_sequence: int,
    content: dict,
) -> Message:
    """
    创建一个 assistant 占位消息（结构化 content），用于文生图/文生视频等“非文本产物”的生成流程。

    - 不更新 conversation 的 last_message_content / unread_count（等最终结果写入时再更新）
    """
    seq = int(user_sequence) + 1
    msg = Message(
        conversation_id=conversation_id,
        role="assistant",
        content=content,
        sequence=seq,
    )
    db.add(msg)
    db.commit()
    db.refresh(msg)
    return msg


def finalize_assistant_message_after_user_sequence(
    db: Session,
    *,
    conversation_id: UUID,
    user_sequence: int,
    content_text: str,
) -> Message:
    """
    将 assistant 占位消息写入最终文本，并同步更新 conversation 的预览与未读计数。
    若占位消息不存在（极端情况），退化为创建一条新的 assistant 消息。
    """
    assistant_seq = int(user_sequence) + 1
    msg = db.execute(
        select(Message).where(
            Message.conversation_id == conversation_id,
            Message.sequence == assistant_seq,
            Message.role == "assistant",
        )
    ).scalars().first()

    if msg is None:
        return create_assistant_message_after_user(
            db,
            conversation_id=conversation_id,
            user_sequence=user_sequence,
            content_text=content_text,
        )

    previous_text = ""
    if isinstance(msg.content, dict):
        previous_text = str(msg.content.get("text") or "")

    msg.content = {"type": "text", "text": content_text}
    db.add(msg)

    conv = db.get(Conversation, conversation_id)
    if conv:
        conv.last_message_content = content_text
        conv.last_activity_at = datetime.now(UTC)
        # 仅在占位为空时补一次未读计数，避免重复累加。
        if not previous_text.strip():
            conv.unread_count += 1
        db.add(conv)

    db.commit()
    db.refresh(msg)
    return msg


def finalize_assistant_image_generation_after_user_sequence(
    db: Session,
    *,
    conversation_id: UUID,
    user_sequence: int,
    content: dict,
    preview_text: str,
) -> Message:
    """
    将 assistant 占位消息写入最终“文生图”内容，并同步更新 conversation 的预览与未读计数。

    - content：结构化 JSON（建议包含 type=image_generation 等信息）
    - preview_text：写入 Conversation.last_message_content 的精简预览文本
    """
    assistant_seq = int(user_sequence) + 1
    msg = db.execute(
        select(Message).where(
            Message.conversation_id == conversation_id,
            Message.sequence == assistant_seq,
            Message.role == "assistant",
        )
    ).scalars().first()

    if msg is None:
        msg = Message(
            conversation_id=conversation_id,
            role="assistant",
            content=content,
            sequence=assistant_seq,
        )
        db.add(msg)
        previous_empty = True
    else:
        previous_empty = False
        if isinstance(msg.content, dict):
            t = str(msg.content.get("text") or "").strip()
            previous_empty = not t
        msg.content = content
        db.add(msg)

    conv = db.get(Conversation, conversation_id)
    if conv:
        conv.last_message_content = (preview_text or "").strip()
        conv.last_activity_at = datetime.now(UTC)
        if previous_empty:
            conv.unread_count += 1
        db.add(conv)

    db.commit()
    db.refresh(msg)
    return msg


def update_assistant_message_for_user_sequence(
    db: Session,
    *,
    conversation_id: UUID,
    user_sequence: int,
    new_text: str,
) -> Message | None:
    assistant_seq = int(user_sequence) + 1
    msg = db.execute(
        select(Message).where(
            Message.conversation_id == conversation_id,
            Message.sequence == assistant_seq,
            Message.role == "assistant",
        )
    ).scalars().first()
    if msg is None:
        return None
    msg.content = {"type": "text", "text": new_text}
    db.add(msg)

    # Update conversation preview
    conv = db.get(Conversation, conversation_id)
    if conv:
        conv.last_message_content = new_text
        db.add(conv)

    return msg


def list_messages_with_run_summaries(
    db: Session,
    *,
    conversation_id: UUID,
    user_id: UUID,
    cursor: str | None = None,
    limit: int = 30,
) -> tuple[list[Message], dict[UUID, list[Run]], str | None]:
    conv = get_conversation_any(db, conversation_id=conversation_id, user_id=user_id)

    # Reset unread count when user views the conversation
    if conv.unread_count > 0:
        conv.unread_count = 0
        db.add(conv)
        db.commit()

    offset = _parse_offset_cursor(cursor)
    limit = max(1, min(int(limit or 30), 100))

    stmt = (
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.sequence.desc())
    )
    rows = list(db.execute(stmt.offset(offset).limit(limit + 1)).scalars().all())
    has_more = len(rows) > limit
    items = rows[:limit]

    message_ids = [UUID(str(m.id)) for m in items if m.role == "user"]
    if not message_ids:
        return items, {}, _next_cursor(offset, limit, has_more=has_more)

    run_rows = db.execute(
        select(Run)
        .where(Run.message_id.in_(message_ids))
        .order_by(Run.created_at.desc())
    ).scalars().all()
    by_message: dict[UUID, list[Run]] = {}
    for run in run_rows:
        key = UUID(str(run.message_id))
        by_message.setdefault(key, []).append(run)

    return items, by_message, _next_cursor(offset, limit, has_more=has_more)


def get_run_detail(db: Session, *, run_id: UUID, user_id: UUID) -> Run:
    run = db.execute(
        select(Run).where(Run.id == run_id, Run.user_id == user_id)
    ).scalars().first()
    if run is None:
        raise not_found("Run 不存在", details={"run_id": str(run_id)})
    return run


def delete_message(
    db: Session,
    *,
    message_id: UUID,
    user_id: UUID,
) -> None:
    msg = db.get(Message, message_id)
    if msg is None:
        raise not_found("消息不存在", details={"message_id": str(message_id)})

    # 权限校验：确保消息所属会话属于当前用户
    get_conversation(db, conversation_id=UUID(str(msg.conversation_id)), user_id=user_id)

    conv = db.get(Conversation, msg.conversation_id)
    db.delete(msg)
    db.commit()

    # 重新计算会话预览
    if conv:
        latest = (
            db.execute(
                select(Message)
                .where(Message.conversation_id == conv.id)
                .order_by(Message.sequence.desc())
                .limit(1)
            )
            .scalars()
            .first()
        )
        if latest and isinstance(latest.content, dict):
            conv.last_message_content = str(latest.content.get("text") or "").strip()
        else:
            conv.last_message_content = ""
        conv.last_activity_at = datetime.now(UTC)
        db.add(conv)
        db.commit()


__all__ = [
    "delete_message",
    "clear_conversation_messages",
    "create_assistant",
    "create_assistant_message_after_user",
    "create_assistant_image_generation_placeholder_after_user",
    "create_assistant_message_placeholder_after_user",
    "create_conversation",
    "create_user_message",
    "delete_assistant",
    "delete_conversation",
    "finalize_assistant_message_after_user_sequence",
    "finalize_assistant_image_generation_after_user_sequence",
    "get_assistant",
    "get_conversation",
    "get_conversation_any",
    "get_run_detail",
    "list_assistants",
    "list_conversations",
    "list_messages_with_run_summaries",
    "update_assistant",
    "update_assistant_message_for_user_sequence",
    "update_conversation",
]
