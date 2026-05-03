from fastapi import APIRouter, Depends
from app.services.usage_service import get_usage_response, get_limits_response
from app.middlewares.auth_middleware import get_current_user
from app.schemas import UsageResponse, PlanLimitsResponse

router = APIRouter(prefix="/api/usage", tags=["Usage"])


@router.get("", response_model=UsageResponse)
async def get_usage(user: dict = Depends(get_current_user)):
    return await get_usage_response(user)


@router.get("/limits", response_model=PlanLimitsResponse)
async def get_limits(user: dict = Depends(get_current_user)):
    return await get_limits_response(user)
