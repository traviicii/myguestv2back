from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware

from app.api.v1.router import api_router
from app.core.config import Settings, get_settings
from app.core.errors import register_error_handlers
from app.core.security import FirebaseTokenVerifier
from app.db.session import build_engine, build_session_maker


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    if settings.is_production and not settings.resolved_trusted_hosts:
        raise ValueError("Production requires TRUSTED_HOSTS to be configured.")

    app = FastAPI(
        title=settings.app_name,
        docs_url="/docs" if settings.expose_api_docs else None,
        redoc_url="/redoc" if settings.expose_api_docs else None,
        openapi_url="/openapi.json" if settings.expose_api_docs else None,
    )

    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=settings.resolved_trusted_hosts,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=settings.cors_allow_credentials,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    engine = build_engine(settings.database_url)
    app.state.engine = engine
    app.state.session_factory = build_session_maker(engine)
    app.state.token_verifier = FirebaseTokenVerifier(settings)

    register_error_handlers(app)
    app.include_router(api_router, prefix="/api/v1")

    @app.get("/")
    def root() -> dict[str, str]:
        return {"status": "ok", "service": settings.app_name}

    return app


app = create_app()
