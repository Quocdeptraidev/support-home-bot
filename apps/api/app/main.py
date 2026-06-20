from fastapi import FastAPI
from fastapi.responses import PlainTextResponse

from app.api.router import api_router
from app.api.routes.facebook_webhook import (
    receive_facebook_webhook,
    verify_facebook_webhook,
)
from app.core.config import settings


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        docs_url="/docs",
        redoc_url="/redoc",
    )
    app.include_router(api_router)

    # Đăng ký trực tiếp endpoint /webhook để tương thích với cấu hình cũ trên Meta Dashboard
    app.get("/webhook", response_class=PlainTextResponse)(verify_facebook_webhook)
    app.post("/webhook", response_class=PlainTextResponse)(receive_facebook_webhook)

    return app


app = create_app()
