from __future__ import annotations

from typing import List

from sqlalchemy import Select, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.logging_config import logger
from app.models import ProviderPreset
from app.schemas.provider_control import (
    ProviderPresetBase,
    ProviderPresetCreateRequest,
    ProviderPresetExportResponse,
    ProviderPresetImportError,
    ProviderPresetImportRequest,
    ProviderPresetImportResult,
    ProviderPresetUpdateRequest,
)


class ProviderPresetServiceError(RuntimeError):
    """Base error for provider preset operations."""


class ProviderPresetIdExistsError(ProviderPresetServiceError):
    """Raised when preset_id already exists."""


class ProviderPresetNotFoundError(ProviderPresetServiceError):
    """Raised when preset_id cannot be found."""


def list_provider_presets(session: Session) -> List[ProviderPreset]:
    stmt: Select[tuple[ProviderPreset]] = select(ProviderPreset).order_by(ProviderPreset.created_at.desc())
    return list(session.execute(stmt).scalars().all())


def get_provider_preset(session: Session, preset_id: str) -> ProviderPreset:
    stmt: Select[tuple[ProviderPreset]] = select(ProviderPreset).where(ProviderPreset.preset_id == preset_id)
    preset = session.execute(stmt).scalars().first()
    if preset is None:
        raise ProviderPresetNotFoundError(f"Preset {preset_id} not found")
    return preset


def create_provider_preset(session: Session, payload: ProviderPresetCreateRequest) -> ProviderPreset:
    preset = ProviderPreset(
        preset_id=payload.preset_id,
        display_name=payload.display_name,
        description=payload.description,
        provider_type=payload.provider_type,
        transport=payload.transport,
        sdk_vendor=payload.sdk_vendor,
        base_url=str(payload.base_url),
        models_path=payload.models_path,
        messages_path=payload.messages_path,
        chat_completions_path=payload.chat_completions_path,
        responses_path=payload.responses_path,
        supported_api_styles=payload.supported_api_styles,
        retryable_status_codes=payload.retryable_status_codes,
        custom_headers=payload.custom_headers,
        static_models=payload.static_models,
    )

    session.add(preset)
    try:
        session.commit()
    except IntegrityError as exc:  # pragma: no cover
        session.rollback()
        logger.error("Failed to create provider preset: %s", exc)
        raise ProviderPresetIdExistsError("preset_id 已存在") from exc

    session.refresh(preset)
    return preset


def update_provider_preset(
    session: Session,
    preset_id: str,
    payload: ProviderPresetUpdateRequest,
) -> ProviderPreset:
    preset = get_provider_preset(session, preset_id)

    if payload.display_name is not None:
        preset.display_name = payload.display_name
    if payload.description is not None:
        preset.description = payload.description
    if payload.provider_type is not None:
        preset.provider_type = payload.provider_type
    if payload.transport is not None:
        preset.transport = payload.transport
    if payload.sdk_vendor is not None:
        preset.sdk_vendor = payload.sdk_vendor
    if payload.base_url is not None:
        preset.base_url = str(payload.base_url)
    if payload.models_path is not None:
        preset.models_path = payload.models_path
    if payload.messages_path is not None:
        preset.messages_path = payload.messages_path
    if payload.chat_completions_path is not None:
        preset.chat_completions_path = payload.chat_completions_path
    if payload.responses_path is not None:
        preset.responses_path = payload.responses_path
    if payload.supported_api_styles is not None:
        preset.supported_api_styles = payload.supported_api_styles
    if payload.retryable_status_codes is not None:
        preset.retryable_status_codes = payload.retryable_status_codes
    if payload.custom_headers is not None:
        preset.custom_headers = payload.custom_headers
    if payload.static_models is not None:
        preset.static_models = payload.static_models

    session.add(preset)
    session.commit()
    session.refresh(preset)
    return preset


def delete_provider_preset(session: Session, preset_id: str) -> None:
    preset = get_provider_preset(session, preset_id)
    session.delete(preset)
    session.commit()


def export_provider_presets(session: Session) -> ProviderPresetExportResponse:
    presets = list_provider_presets(session)
    serialized = [ProviderPresetBase.model_validate(preset) for preset in presets]
    return ProviderPresetExportResponse(presets=serialized, total=len(serialized))


def import_provider_presets(session: Session, payload: ProviderPresetImportRequest) -> ProviderPresetImportResult:
    result = ProviderPresetImportResult()

    for preset_payload in payload.presets:
        try:
            try:
                existing = get_provider_preset(session, preset_payload.preset_id)
            except ProviderPresetNotFoundError:
                existing = None

            if existing and not payload.overwrite:
                result.skipped.append(preset_payload.preset_id)
                continue

            if existing and payload.overwrite:
                update_payload = ProviderPresetUpdateRequest(
                    **preset_payload.model_dump(exclude={"preset_id"})
                )
                update_provider_preset(session, preset_payload.preset_id, update_payload)
                result.updated.append(preset_payload.preset_id)
                continue

            create_payload = ProviderPresetCreateRequest(**preset_payload.model_dump())
            create_provider_preset(session, create_payload)
            result.created.append(preset_payload.preset_id)
        except ProviderPresetServiceError as exc:
            session.rollback()
            logger.error("Failed to import provider preset %s: %s", preset_payload.preset_id, exc)
            result.failed.append(
                ProviderPresetImportError(preset_id=preset_payload.preset_id, reason=str(exc))
            )
        except Exception as exc:  # pragma: no cover - unexpected branch
            session.rollback()
            logger.exception(
                "Unexpected error importing provider preset %s", preset_payload.preset_id
            )
            result.failed.append(
                ProviderPresetImportError(preset_id=preset_payload.preset_id, reason=str(exc))
            )

    return result


__all__ = [
    "ProviderPresetServiceError",
    "ProviderPresetIdExistsError",
    "ProviderPresetNotFoundError",
    "create_provider_preset",
    "update_provider_preset",
    "delete_provider_preset",
    "list_provider_presets",
    "get_provider_preset",
    "export_provider_presets",
    "import_provider_presets",
]
