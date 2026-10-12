from fastapi import APIRouter

from app.api.routes import networks, journeys

api_router = APIRouter(prefix="/api")

api_router.include_router(networks.router)
api_router.include_router(journeys.router)
