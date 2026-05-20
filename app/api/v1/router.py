from fastapi import APIRouter

from app.api.v1.endpoints import (
    account,
    auth,
    client_groups,
    clients,
    color_charts,
    exports,
    formulas,
    health,
    metrics,
    services,
)

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(account.router)
api_router.include_router(clients.router)
api_router.include_router(client_groups.router)
api_router.include_router(color_charts.router)
api_router.include_router(formulas.router)
api_router.include_router(exports.router)
api_router.include_router(metrics.router)
api_router.include_router(services.router)
