from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from app.schemas import (
    RegisterRequest, LoginRequest, GoogleAuthRequest,
    RefreshTokenRequest, AuthResponse, UserResponse,
)
from app.services import auth_service
from app.middlewares.auth_middleware import get_current_user

router = APIRouter(prefix="/api/auth", tags=["Auth"])


@router.post("/register", response_model=AuthResponse, status_code=201)
async def register(body: RegisterRequest):
    return await auth_service.register_user(body)


@router.post("/login", response_model=AuthResponse)
async def login(body: LoginRequest):
    return await auth_service.login_user(body)


@router.post("/google", response_model=AuthResponse)
async def google_sso(body: GoogleAuthRequest):
    return await auth_service.google_sso(body)


@router.post("/refresh-token")
async def refresh_token(body: RefreshTokenRequest):
    tokens = await auth_service.refresh_tokens(body.refreshToken)
    return tokens


@router.post("/logout", status_code=204)
async def logout(current_user: dict = Depends(get_current_user)):
    await auth_service.logout_user(str(current_user["_id"]))


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: dict = Depends(get_current_user)):
    return UserResponse(
        id=str(current_user["_id"]),
        name=current_user["name"],
        email=current_user["email"],
        avatarUrl=current_user.get("avatarUrl"),
        role=current_user["role"],
        plan=current_user["plan"],
        createdAt=current_user["createdAt"],
    )
