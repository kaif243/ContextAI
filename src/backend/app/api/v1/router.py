"""API v1 router - main router combining all endpoints."""

from fastapi import APIRouter

from app.api.v1.endpoints import health, settings, clipboard, files, screen

api_router = APIRouter()

# Include all endpoint routers
api_router.include_router(health.router, prefix="/health", tags=["Health"])
api_router.include_router(settings.router, prefix="/settings", tags=["Settings"])
api_router.include_router(clipboard.router, prefix="/clipboard", tags=["Clipboard"])
api_router.include_router(files.router, prefix="/files", tags=["Files"])
api_router.include_router(screen.router, prefix="/screen", tags=["Screen"])
