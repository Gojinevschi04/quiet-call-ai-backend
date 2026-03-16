from typing import Annotated

import bcrypt
import jwt
from fastapi import Depends, HTTPException, status

from app.modules.auth.auth_handler import create_access_token, create_refresh_token, create_reset_token, decode_token
from app.modules.auth.schema import TokenResponse
from app.modules.users.models import User
from app.modules.users.repository import UserRepository


class AuthService:
    def __init__(
        self,
        user_repository: Annotated[UserRepository, Depends(UserRepository)],
    ) -> None:
        self.user_repository = user_repository

    @staticmethod
    def hash_password(password: str) -> str:
        return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

    @staticmethod
    def verify_password(plain_password: str, hashed_password: str) -> bool:
        return bcrypt.checkpw(plain_password.encode(), hashed_password.encode())

    async def authenticate_user(self, email: str, password: str) -> User:
        user = await self.user_repository.get_by_email(email)
        if not user or not user.hashed_password:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")
        if not self.verify_password(password, user.hashed_password):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")
        return user

    @staticmethod
    def create_tokens(user_id: int) -> TokenResponse:
        return TokenResponse(
            access_token=create_access_token(user_id),
            refresh_token=create_refresh_token(user_id),
        )

    @staticmethod
    def create_reset_token(user_id: int) -> str:
        return create_reset_token(user_id)

    @staticmethod
    def refresh_access_token(refresh_token: str) -> TokenResponse:
        try:
            payload = decode_token(refresh_token)
        except jwt.ExpiredSignatureError:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token expired")
        except jwt.InvalidTokenError:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")

        if payload.get("type") != "refresh":
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token type")

        user_id = int(payload["sub"])
        return TokenResponse(
            access_token=create_access_token(user_id),
            refresh_token=create_refresh_token(user_id),
        )
