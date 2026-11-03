from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app import auth
from app.ai.provider import AIServiceError
from app.config import get_settings
from app.db import create_db_and_tables
from app.routers import essays, topics
from app.services.usage import QuotaExceeded


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    if settings.local_mode and settings.cookie_secure:
        raise RuntimeError("LOCAL_MODE lets anyone in without login. It must be off in production (COOKIE_SECURE=true).")
    create_db_and_tables()
    yield


app = FastAPI(title="Essay Coach API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(AIServiceError)
def ai_error_handler(request: Request, exc: AIServiceError) -> JSONResponse:
    return JSONResponse(status_code=503, content={"detail": str(exc)})


@app.exception_handler(QuotaExceeded)
def quota_error_handler(request: Request, exc: QuotaExceeded) -> JSONResponse:
    return JSONResponse(status_code=429, content={"detail": str(exc)})


@app.get("/health", tags=["meta"])
def health() -> dict:
    return {"status": "ok"}


app.include_router(auth.router)
app.include_router(topics.router)
app.include_router(essays.router)
