from fastapi import APIRouter, Depends
from app.services.llm_service import get_available_models
from app.middlewares.auth_middleware import get_current_user
from app.schemas import ModelsResponse, SelectModelRequest, MessageOut
from app.core.config import settings

router = APIRouter(prefix="/api/models", tags=["Models"])


@router.get("", response_model=ModelsResponse)
async def list_models(user: dict = Depends(get_current_user)):
    models = await get_available_models()
    # Ensure at least the default model appears
    if not models:
        models = [{
            "id": settings.default_model,
            "name": settings.default_model,
            "provider": settings.llm_provider,
            "isAvailable": False,
            "contextLength": None,
        }]
    return ModelsResponse(models=models, defaultModel=settings.default_model)


@router.post("/select", response_model=MessageOut)
async def select_model(body: SelectModelRequest, user: dict = Depends(get_current_user)):
    # In a full implementation you'd persist the user's preferred model
    return MessageOut(message=f"Model preference set to '{body.model}'")
