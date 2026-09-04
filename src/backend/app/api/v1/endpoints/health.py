"""Health check endpoint."""

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.classification import get_activity_classifier
from app.core.database import get_db
from app.core.config import settings, llm_settings
from app.core.logging import get_logger
from app.ocr import get_ocr_provider

logger = get_logger(__name__)

router = APIRouter()


class ServiceStatus(BaseModel):
    """Status of individual services."""

    database: bool
    vector_store: bool
    ml_models: bool
    ocr: bool
    activity_classifier: bool


class HealthResponse(BaseModel):
    """Health check response model."""

    status: str
    version: str
    timestamp: str
    services: ServiceStatus
    environment: str


def check_database_health(db: Session) -> bool:
    """Check if database is accessible."""
    try:
        db.execute("SELECT 1")
        return True
    except Exception as e:
        logger.warning(f"Database health check failed: {e}")
        return False


def check_services_health() -> dict[str, bool]:
    """
    Check health of all services.

    Returns:
        Dictionary with service health status.
    """
    try:
        ocr_available = get_ocr_provider().is_available()
    except Exception:  # noqa: BLE001
        ocr_available = False
    try:
        classifier_available = get_activity_classifier().is_available()
    except Exception:  # noqa: BLE001
        classifier_available = False

    services = {
        "database": True,  # checked separately in endpoint
        "vector_store": False,  # Phase 6
        "ml_models": False,  # Phase 5
        "ocr": ocr_available,
        "activity_classifier": classifier_available,
    }
    return services


@router.get("", response_model=HealthResponse)
async def health_check(db: Session = Depends(get_db)) -> HealthResponse:
    """
    Health check endpoint for the ContextAI backend.

    Returns the overall health status and individual service statuses.
    """
    # Check database
    db_healthy = check_database_health(db)

    # Check all services
    services = check_services_health()
    services["database"] = db_healthy

    # Determine overall status
    all_healthy = all(services.values())
    status = "healthy" if all_healthy else "degraded"

    return HealthResponse(
        status=status,
        version=settings.app_version,
        timestamp=datetime.now(timezone.utc).isoformat(),
        services=ServiceStatus(**services),
        environment=settings.environment,
    )


@router.get("/detailed")
async def detailed_health_check(db: Session = Depends(get_db)) -> dict[str, Any]:
    """
    Detailed health check with more information.

    Returns additional diagnostic information.
    """
    db_healthy = check_database_health(db)
    services = check_services_health()
    services["database"] = db_healthy

    return {
        "status": "healthy" if all(services.values()) else "degraded",
        "version": settings.app_version,
        "environment": settings.environment,
        "debug": settings.debug,
        "services": services,
        "config": {
            "llm_provider": llm_settings.provider,
            "llm_model": llm_settings.model,
            "privacy_mode": settings.privacy_mode,
        },
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
