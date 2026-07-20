from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.v1.router import api_router
from app.core.config import settings
from app.core.exceptions import AppException
from app.core.logging import configure_logging
from app.core.observability import (
    setup_observability,
    start_dependency_probes,
    stop_dependency_probes,
)
from app.middlewares.request_context import RequestContextMiddleware

configure_logging()


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    probe_task = start_dependency_probes()
    try:
        yield
    finally:
        await stop_dependency_probes(probe_task)


app = FastAPI(
    title=f"{settings.app_name} API",
    version="1.0.0",
    description="EduFlow 智慧学习平台开放接口",
    lifespan=lifespan,
)
app.add_middleware(RequestContextMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(api_router, prefix="/api/v1")
setup_observability(app)


@app.exception_handler(AppException)
async def app_exception_handler(request: Request, exc: AppException) -> JSONResponse:
    headers = None
    if exc.status_code == 429 and isinstance(exc.data, dict):
        headers = {"Retry-After": str(exc.data.get("retry_after", 1))}
    return JSONResponse(
        status_code=exc.status_code,
        headers=headers,
        content={
            "code": exc.code,
            "message": exc.message,
            "data": exc.data,
            "request_id": getattr(request.state, "request_id", ""),
        },
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content={
            "code": 10001,
            "message": "请求参数校验失败",
            "data": jsonable_encoder(exc.errors()),
            "request_id": getattr(request.state, "request_id", ""),
        },
    )
