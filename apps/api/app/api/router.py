from fastapi import APIRouter

from app.api.routes.facebook_webhook import router as facebook_webhook_router
from app.api.routes.health import router as health_router

api_router = APIRouter()
api_router.include_router(health_router)
api_router.include_router(facebook_webhook_router)
