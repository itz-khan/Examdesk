"""
ExamDesk — FastAPI Application Entry Point
Wires together all routers, middleware, and startup hooks.
"""

import logging
import os
import socket
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

from config import settings
from database.session import create_tables, engine
from database.redis_client import connect_redis, disconnect_redis, get_redis
from middleware.logging import GlobalExceptionMiddleware, RequestLoggingMiddleware

# ── Routers ────────────────────────────────────────────────────────────────
from api.routes.auth import router as auth_router
from api.routes.users import router as users_router
from api.routes.subjects import subjects_router, audit_router
from api.routes.questions import router as questions_router
from api.routes.exams import router as exams_router
from api.routes.attempts import router as attempts_router
from api.routes.results import router as results_router
from api.routes.analytics import (
    analytics_router,
    leaderboard_router,
    notifications_router,
    certificates_router,
)

# ── Logging setup ──────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.DEBUG if settings.DEBUG else logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("examdesk")


# ── Lifespan ───────────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("🚀 ExamDesk starting up...")
    if settings.ENVIRONMENT == "development":
        await create_tables()
        logger.info("✅ Database tables verified")
    await connect_redis()
    yield
    await disconnect_redis()
    logger.info("🛑 ExamDesk shutting down...")


# ── App factory ────────────────────────────────────────────────────────────
def create_app() -> FastAPI:
    app = FastAPI(
        title="ExamDesk API",
        description=(
            "Production-grade Online Examination Platform API. "
            "Supports student, instructor, and admin roles with full exam lifecycle management."
        ),
        version=settings.APP_VERSION,
        docs_url="/api/docs",
        redoc_url="/api/redoc",
        openapi_url="/api/openapi.json",
        lifespan=lifespan,
    )

    # ── CORS ──────────────────────────────────────────────────────
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_origin_regex=r"https://examdesk.*\.vercel\.app",
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Correlation-ID", "X-Response-Time", "X-Instance-ID"],
    )

    # ── Custom middleware ──────────────────────────────────────────
    app.add_middleware(GlobalExceptionMiddleware)
    app.add_middleware(RequestLoggingMiddleware)

    # ── API v1 routers ─────────────────────────────────────────────
    PREFIX = "/api/v1"

    app.include_router(auth_router,          prefix=PREFIX)
    app.include_router(users_router,         prefix=PREFIX)
    app.include_router(subjects_router,      prefix=PREFIX)
    app.include_router(questions_router,     prefix=PREFIX)
    app.include_router(exams_router,         prefix=PREFIX)
    app.include_router(attempts_router,      prefix=PREFIX)
    app.include_router(results_router,       prefix=PREFIX)
    app.include_router(analytics_router,     prefix=PREFIX)
    app.include_router(leaderboard_router,   prefix=PREFIX)
    app.include_router(notifications_router, prefix=PREFIX)
    app.include_router(certificates_router,  prefix=PREFIX)
    app.include_router(audit_router,         prefix=PREFIX)

    # ── System endpoints (multi-instance / load-balancer friendly) ─
    @app.get("/health", tags=["System"])
    async def health():
        """Liveness: process is up. Safe for frequent ALB pings."""
        return {
            "status": "ok",
            "version": settings.APP_VERSION,
            "env": settings.ENVIRONMENT,
            "instance_id": settings.resolved_instance_id,
        }

    @app.get("/ready", tags=["System"])
    async def ready():
        """
        Readiness: can this instance serve exam traffic?
        Checks shared PostgreSQL. Redis is optional (cache only).
        Use this as the ALB target-group health check path.
        """
        checks = {"database": False, "redis": "skipped"}
        try:
            async with engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
            checks["database"] = True
        except Exception as exc:
            logger.warning("Readiness DB check failed on %s: %s", settings.resolved_instance_id, exc)
            return JSONResponse(
                status_code=503,
                content={
                    "status": "not_ready",
                    "instance_id": settings.resolved_instance_id,
                    "checks": checks,
                    "detail": "database unavailable",
                },
            )

        redis_client = get_redis()
        if redis_client is not None:
            try:
                await redis_client.ping()
                checks["redis"] = True
            except Exception:
                checks["redis"] = False  # optional — still ready

        return {
            "status": "ready",
            "instance_id": settings.resolved_instance_id,
            "checks": checks,
        }

    @app.get("/server-identity", tags=["System"])
    async def server_identity(request: Request):
        """
        Shows which backend instance handled the request.
        Useful when demonstrating ALB routing across EC2 instances.
        """
        return {
            "instance_id": settings.resolved_instance_id,
            "hostname": socket.gethostname(),
            "pid": os.getpid(),
            "version": settings.APP_VERSION,
            "env": settings.ENVIRONMENT,
            "listen_port": request.url.port,
        }

    @app.get("/", tags=["System"], include_in_schema=False)
    async def root():
        return {"message": "ExamDesk API", "docs": "/api/docs", "health": "/health", "ready": "/ready"}

    return app


app = create_app()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
        workers=1 if settings.DEBUG else settings.WORKERS,
        log_level="debug" if settings.DEBUG else "info",
    )