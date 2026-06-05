import os
import secrets
import logging
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from typing import Optional

from app.auth import create_access_token, require_auth

logger = logging.getLogger(__name__)

router = APIRouter()

API_USERNAME = os.getenv("API_USERNAME", "admin")
API_PASSWORD = os.getenv("API_PASSWORD", "admin")


class LoginRequest(BaseModel):
    username: str = Field(...)
    password: str = Field(...)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


@router.post("/login", response_model=TokenResponse)
def login(req: LoginRequest):
    if not secrets.compare_digest(req.username, API_USERNAME) or not secrets.compare_digest(
        req.password, API_PASSWORD
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        )
    token = create_access_token({"sub": req.username})
    logger.info("User '%s' logged in", req.username)
    return TokenResponse(access_token=token)


@router.get("/verify")
def verify(auth: dict = Depends(require_auth)):
    return {"status": "ok", "user": auth.get("sub")}
