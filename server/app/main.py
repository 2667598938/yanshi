import secrets
import asyncio
import logging
from contextlib import suppress
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import BASE_DIR, Settings
from .database import make_database
from .errors import install_errors, ok
from .services.persistent_transient import PersistentTransientStore
from .routers import (
    auth,
    room_media,
    admin,
    public,
    sync,
    room,
    attachments,
    schools,
    ai,
    vip,
    error_types,
    oauth,
    messages,
    resources,
    resource_review,
    posts,
    inspirations,
    rooms,
    phone,
    group,
    time_nodes,
    timer,
    group_admission,
)


def resolve_secret(settings: Settings) -> str:
    if settings.jwt_secret:
        return settings.jwt_secret
    if settings.environment == "production":
        raise RuntimeError("生产环境必须设置 JWT_SECRET")
    key_path = BASE_DIR / "data" / "jwt.key"
    key_path.parent.mkdir(parents=True, exist_ok=True)
    if not key_path.exists():
        key_path.write_text(secrets.token_hex(48), encoding="utf-8")
    return key_path.read_text(encoding="utf-8").strip()


@asynccontextmanager
async def lifespan(app: FastAPI):
    async def maintenance_loop():
        from .services.maintenance import run_maintenance

        while True:
            try:
                await asyncio.to_thread(
                    run_maintenance,
                    app.state.session_factory,
                    app.state.settings,
                    app.state.secret,
                )
            except Exception:
                logging.getLogger("yanshi.maintenance").exception(
                    "Maintenance cycle failed"
                )
            await asyncio.sleep(30)

    job = asyncio.create_task(maintenance_loop())
    try:
        yield
    finally:
        job.cancel()
        with suppress(asyncio.CancelledError):
            await job


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()
    engine, sessions = make_database(settings.database_url)
    app = FastAPI(
        title="研时 API",
        version="0.3.0",
        docs_url="/docs",
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )

    app.state.settings = settings
    app.state.engine = engine
    app.state.session_factory = sessions
    app.state.secret = resolve_secret(settings)
    app.state.transient = PersistentTransientStore(
        sessions, settings.ai_key_enc_secret or app.state.secret
    )

    install_errors(app)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def security_headers(request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "same-origin"
        response.headers["Permissions-Policy"] = (
            "camera=(self), microphone=(self), geolocation=()"
        )
        return response

    @app.get("/health")
    def health():
        return {"status": "ok"}

    @app.get("/health/ready")
    def ready():
        from fastapi.responses import JSONResponse
        from .services.readiness import database_ready

        healthy = database_ready(app.state.engine)
        return JSONResponse(
            {"status": "ready" if healthy else "not_ready"},
            status_code=200 if healthy else 503,
        )

    @app.get("/api/v1/ping")
    def ping():
        return ok({"site": "研时", "version": "0.3.0"})

    app.include_router(group_admission.router)
    app.include_router(timer.router)
    app.include_router(public.router)
    app.include_router(auth.router)
    app.include_router(room_media.router)
    app.include_router(oauth.router)
    app.include_router(phone.router)
    app.include_router(group.router)
    app.include_router(time_nodes.router)
    app.include_router(sync.router)
    app.include_router(room.router)
    app.include_router(rooms.router)
    app.include_router(attachments.router)
    app.include_router(schools.router)
    app.include_router(ai.router)
    app.include_router(error_types.router)
    app.include_router(vip.router)
    app.include_router(messages.router)
    app.include_router(resources.router)
    app.include_router(resource_review.router)
    app.include_router(posts.router)
    app.include_router(inspirations.router)
    app.include_router(admin.router)
    return app


app = create_app()
