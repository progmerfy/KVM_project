import os
import secrets
import logging
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field
from typing import Optional

from app.auth import create_access_token, get_current_user, require_auth
from app.database import (
    verify_password,
    get_user_by_username,
    create_user,
    list_users,
)

logger = logging.getLogger(__name__)

router = APIRouter()


class LoginRequest(BaseModel):
    username: str = Field(...)
    password: str = Field(...)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class RegisterRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=32)
    password: str = Field(..., min_length=4, max_length=128)
    is_admin: bool = False


@router.get("/login-page", response_class=HTMLResponse)
def login_page(redirect: str = "/"):
    return HTMLResponse(content=_LOGIN_PAGE_HTML.format(redirect=redirect))


@router.post("/login", response_model=TokenResponse)
def login(req: LoginRequest):
    try:
        user = get_user_by_username(req.username)
    except Exception:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)

    if not user or not verify_password(req.password, user["password_hash"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        )
    token = create_access_token({"sub": req.username, "user_id": user["id"]})
    logger.info("User '%s' logged in", req.username)
    return TokenResponse(access_token=token)


@router.get("/verify")
def verify(auth: dict = Depends(require_auth)):
    return {"status": "ok", "user": auth.get("sub"), "user_id": auth.get("user_id")}


@router.post("/register")
def register(req: RegisterRequest, current_user: dict = Depends(get_current_user)):
    if not current_user.get("is_admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
    try:
        user = create_user(req.username, req.password, req.is_admin)
        logger.info("Admin '%s' created user '%s'", current_user["username"], req.username)
        return {"status": "ok", "user": user}
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))


@router.get("/users")
def list_all_users(current_user: dict = Depends(get_current_user)):
    if not current_user.get("is_admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
    return {"status": "ok", "users": list_users()}


@router.get("/me")
def me(current_user: dict = Depends(get_current_user)):
    return {
        "status": "ok",
        "user": {
            "id": current_user["id"],
            "username": current_user["username"],
            "is_admin": bool(current_user["is_admin"]),
        },
    }


_LOGIN_PAGE_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>KVM Manager - Login</title>
<style>
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{
    background: #0a0a0f; color: #e4e4e7; font-family: 'Inter', system-ui, sans-serif;
    display: flex; justify-content: center; align-items: center; height: 100vh;
  }}
  .login-box {{
    background: #12121a; padding: 40px; border-radius: 10px; width: 360px;
    border: 1px solid #1e1e32;
  }}
  h1 {{ font-size: 20px; margin-bottom: 24px; color: #fff; text-align: center; }}
  label {{ display: block; margin-bottom: 6px; font-size: 13px; color: #71717a; }}
  input {{
    width: 100%; padding: 10px 12px; margin-bottom: 16px;
    background: #0a0a0f; border: 1px solid #1e1e32; border-radius: 6px;
    color: #fff; font-size: 14px; font-family: inherit;
  }}
  input:focus {{ outline: none; border-color: #60a5fa; }}
  button {{
    width: 100%; padding: 10px; background: #60a5fa; color: #000;
    border: none; border-radius: 6px; font-size: 14px; font-weight: 600;
    cursor: pointer; font-family: inherit;
  }}
  button:hover {{ opacity: 0.9; }}
  .error {{ color: #ef4444; font-size: 13px; margin-bottom: 12px; display: none; text-align: center; }}
</style>
</head>
<body>
<div class="login-box">
  <h1>KVM Manager</h1>
  <div class="error" id="error">Invalid credentials</div>
  <form id="login-form">
    <label for="username">Username</label>
    <input type="text" id="username" value="admin" autocomplete="username">
    <label for="password">Password</label>
    <input type="password" id="password" value="admin" autocomplete="current-password">
    <button type="submit">Sign In</button>
  </form>
</div>
<script>
document.getElementById('login-form').addEventListener('submit', async (e) => {{
  e.preventDefault();
  const username = document.getElementById('username').value;
  const password = document.getElementById('password').value;
  const errEl = document.getElementById('error');
  try {{
    const resp = await fetch('/auth/login', {{
      method: 'POST',
      headers: {{ 'Content-Type': 'application/json' }},
      body: JSON.stringify({{ username, password }}),
    }});
    if (!resp.ok) {{ errEl.style.display = 'block'; return; }}
    const data = await resp.json();
    localStorage.setItem('token', data.access_token);
    const params = new URLSearchParams(location.search);
    window.location.href = params.get('redirect') || '/';
  }} catch(e) {{
    errEl.textContent = 'Connection error';
    errEl.style.display = 'block';
  }}
}});
</script>
</body>
</html>"""
