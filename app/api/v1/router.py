from fastapi import APIRouter

from app.api.v1.endpoints import auth, clients, color_charts, formulas, health, services

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(clients.router)
api_router.include_router(color_charts.router)
api_router.include_router(formulas.router)
api_router.include_router(services.router)
