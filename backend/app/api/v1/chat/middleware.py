"""
请求/响应中间件：内容审核、预处理等
"""

import json
from collections.abc import AsyncIterator, Callable
from typing import Any

from fastapi import HTTPException, status

from app.auth import AuthenticatedAPIKey
from app.services.audit_service import record_audit_event
from app.services.compliance_service import apply_content_policy, findings_to_summary
from app.settings import settings


def enforce_request_moderation(
    payload: dict[str, Any],
    *,
    session_id: str | None,
    api_key: AuthenticatedAPIKey,
    logical_model: str | None = None,
) -> None:
    """请求内容审核"""
    if not settings.enable_content_moderation:
        return

    result = apply_content_policy(
        payload,
        action=settings.content_moderation_action,
        mask_token=settings.content_moderation_mask_token,
        mask_output=False,
    )

    if result.findings:
        record_audit_event(
            action="content_check",
            stage="request",
            user_id=api_key.user_id,
            api_key_id=api_key.id,
            logical_model=logical_model,
            provider_id=None,
            session_id=session_id,
            status_code=None,
            decision="blocked" if result.blocked else "allowed",
            findings=result.findings,
        )

    if result.blocked:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "CONTENT_BLOCKED",
                "message": "请求包含敏感信息，已被内容审核阻断",
                "findings": findings_to_summary(result.findings),
            },
        )


def apply_response_moderation(
    content: Any,
    *,
    session_id: str | None,
    api_key: AuthenticatedAPIKey,
    logical_model: str | None,
    provider_id: str | None,
    status_code: int | None = None,
) -> Any:
    """响应内容审核"""
    if not settings.enable_content_moderation:
        return content

    result = apply_content_policy(
        content,
        action=settings.content_moderation_action,
        mask_token=settings.content_moderation_mask_token,
        mask_output=settings.content_moderation_mask_response,
    )

    if result.findings:
        record_audit_event(
            action="content_check",
            stage="response",
            user_id=api_key.user_id,
            api_key_id=api_key.id,
            logical_model=logical_model,
            provider_id=provider_id,
            session_id=session_id,
            status_code=status_code,
            decision="blocked" if result.blocked else "allowed",
            findings=result.findings,
        )

    if result.blocked:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "CONTENT_BLOCKED",
                "message": "响应包含敏感信息，已被内容审核阻断",
                "findings": findings_to_summary(result.findings),
            },
        )

    if settings.content_moderation_mask_response and result.findings:
        return result.redacted

    return content


async def wrap_stream_with_moderation(
    iterator: AsyncIterator[bytes],
    *,
    session_id: str | None,
    api_key: AuthenticatedAPIKey,
    logical_model: str | None,
    provider_id: str | None,
    provider_id_getter: Callable[[], str | None] | None = None,
) -> AsyncIterator[bytes]:
    """流式响应内容审核"""
    if not settings.enable_content_moderation:
        async for chunk in iterator:
            yield chunk
        return

    async for chunk in iterator:
        effective_provider_id = provider_id
        if effective_provider_id is None and provider_id_getter is not None:
            try:
                effective_provider_id = provider_id_getter()
            except Exception:
                effective_provider_id = provider_id
        text = chunk.decode("utf-8", errors="ignore")
        result = apply_content_policy(
            text,
            action=settings.content_moderation_action,
            mask_token=settings.content_moderation_mask_token,
            mask_output=settings.content_moderation_mask_stream,
        )

        if result.findings:
            record_audit_event(
                action="content_check",
                stage="response_stream",
                user_id=api_key.user_id,
                api_key_id=api_key.id,
                logical_model=logical_model,
                provider_id=effective_provider_id,
                session_id=session_id,
                status_code=None,
                decision="blocked" if result.blocked else "allowed",
                findings=result.findings,
            )

        if result.blocked:
            error_payload = {
                "error": {
                    "code": "CONTENT_BLOCKED",
                    "message": "流式响应包含敏感信息，已被阻断",
                    "findings": findings_to_summary(result.findings),
                }
            }
            yield f"data: {json.dumps(error_payload, ensure_ascii=False)}\n\n".encode()
            return

        if settings.content_moderation_mask_stream and result.findings:
            yield result.redacted.encode("utf-8")
        else:
            yield chunk
