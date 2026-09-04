"""Settings endpoint."""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.logging import get_logger
from app.core.security import get_permission_level, PermissionLevel
from app.models.settings import Settings as SettingsModel

logger = get_logger(__name__)

router = APIRouter()


# Pydantic models
class SettingsResponse(BaseModel):
    """Settings response model."""

    hotkey: str
    auto_start: bool
    minimize_to_tray: bool
    privacy_mode: bool
    clipboard_monitoring: bool
    screen_monitoring: bool
    file_indexing_enabled: bool
    llm_provider: str
    llm_model: str
    log_level: str
    # Phase 3 — Clipboard Intelligence
    clipboard_history_enabled: bool = True
    clipboard_max_bytes: int = 200_000
    clipboard_store_sensitive: bool = False
    clipboard_keep_raw_when_sensitive: bool = False


class SettingsUpdateRequest(BaseModel):
    """Settings update request model."""

    hotkey: str | None = None
    auto_start: bool | None = None
    minimize_to_tray: bool | None = None
    privacy_mode: bool | None = None
    clipboard_monitoring: bool | None = None
    screen_monitoring: bool | None = None
    file_indexing_enabled: bool | None = None
    llm_provider: str | None = None
    llm_model: str | None = None
    log_level: str | None = None
    # Phase 3 — Clipboard Intelligence
    clipboard_history_enabled: bool | None = None
    clipboard_max_bytes: int | None = None
    clipboard_store_sensitive: bool | None = None
    clipboard_keep_raw_when_sensitive: bool | None = None


def get_or_create_settings(db: Session) -> SettingsModel:
    """Get existing settings or create default settings."""
    settings = db.query(SettingsModel).first()
    if settings is None:
        settings = SettingsModel()
        db.add(settings)
        db.commit()
        db.refresh(settings)
    return settings


def _to_response(settings: SettingsModel) -> SettingsResponse:
    return SettingsResponse(
        hotkey=settings.hotkey,
        auto_start=settings.auto_start,
        minimize_to_tray=settings.minimize_to_tray,
        privacy_mode=settings.privacy_mode,
        clipboard_monitoring=settings.clipboard_monitoring,
        screen_monitoring=settings.screen_monitoring,
        file_indexing_enabled=settings.file_indexing_enabled,
        llm_provider=settings.llm_provider,
        llm_model=settings.llm_model,
        log_level=settings.log_level,
        clipboard_history_enabled=settings.clipboard_history_enabled,
        clipboard_max_bytes=settings.clipboard_max_bytes,
        clipboard_store_sensitive=settings.clipboard_store_sensitive,
        clipboard_keep_raw_when_sensitive=settings.clipboard_keep_raw_when_sensitive,
    )


@router.get("", response_model=SettingsResponse)
async def get_settings(db: Session = Depends(get_db)) -> SettingsResponse:
    """
    Get current application settings.

    Returns the current settings for the application.
    """
    settings = get_or_create_settings(db)
    return _to_response(settings)


@router.patch("", response_model=SettingsResponse)
async def update_settings(
    request: SettingsUpdateRequest,
    db: Session = Depends(get_db),
) -> SettingsResponse:
    """
    Update application settings.

    Validates permission level for sensitive settings changes.
    """
    settings = get_or_create_settings(db)

    # Check permissions for sensitive settings
    if request.privacy_mode is not None:
        permission = get_permission_level("modify_system")
        if permission == PermissionLevel.RED:
            logger.info("Privacy mode change requires logging")

    # Update settings
    update_data = request.model_dump(exclude_unset=True)
    # Validate clipboard_max_bytes so the API cannot set a negative
    # or absurdly large value.
    if "clipboard_max_bytes" in update_data and update_data["clipboard_max_bytes"] is not None:
        v = int(update_data["clipboard_max_bytes"])
        if v < 64 or v > 50_000_000:
            from fastapi import HTTPException

            raise HTTPException(
                status_code=400,
                detail="clipboard_max_bytes must be between 64 and 50,000,000",
            )
        update_data["clipboard_max_bytes"] = v
    for field, value in update_data.items():
        if hasattr(settings, field) and value is not None:
            setattr(settings, field, value)

    db.commit()
    db.refresh(settings)

    logger.info(f"Settings updated: {list(update_data.keys())}")

    return _to_response(settings)
