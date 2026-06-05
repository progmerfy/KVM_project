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
    get_user_by_login,
    create_user,
    list_users,
    update_password,
)

logger = logging.getLogger(__name__)

router = APIRouter()


class LoginRequest(BaseModel):
    username: str = Field(..., description="Username or email")
    password: str = Field(...)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class RegisterRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=32)
    password: str = Field(..., min_length=8, max_length=128)
    email: str = Field(None, max_length=128)
    is_admin: bool = False


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(...)
    new_password: str = Field(..., min_length=8, max_length=128)


@router.get("/login-page", response_class=HTMLResponse)
def login_page(redirect: str = "/"):
    return HTMLResponse(content=_LOGIN_PAGE_HTML.format(redirect=redirect))


@router.post("/login", response_model=TokenResponse)
def login(req: LoginRequest):
    try:
        user = get_user_by_login(req.username)
    except Exception:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)

    if not user or not verify_password(req.password, user["password_hash"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        )
    token = create_access_token({"sub": user["username"], "user_id": user["id"]})
    logger.info("User '%s' logged in via '%s'", user["username"], req.username)
    return TokenResponse(access_token=token)


@router.get("/verify")
def verify(auth: dict = Depends(require_auth)):
    return {"status": "ok", "user": auth.get("sub"), "user_id": auth.get("user_id")}


@router.post("/register", response_model=TokenResponse)
def register(req: RegisterRequest):
    try:
        user = create_user(req.username, req.password, is_admin=False, email=req.email)
        logger.info("User '%s' registered", req.username)
        token = create_access_token({"sub": user["username"], "user_id": user["id"]})
        return TokenResponse(access_token=token)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))


@router.post("/register-admin")
def register_admin(req: RegisterRequest, current_user: dict = Depends(get_current_user)):
    if not current_user.get("is_admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
    try:
        user = create_user(req.username, req.password, req.is_admin, req.email)
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
            "email": current_user.get("email"),
            "is_admin": bool(current_user["is_admin"]),
        },
    }


@router.post("/change-password")
def change_password(req: ChangePasswordRequest, current_user: dict = Depends(get_current_user)):
    user = get_user_by_login(current_user["username"])
    if not user or not verify_password(req.current_password, user["password_hash"]):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect",
        )
    update_password(current_user["id"], req.new_password)
    logger.info("Password changed for user '%s'", current_user["username"])
    return {"status": "ok"}


_LOGIN_PAGE_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>KVM Manager</title>
<style>
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{
    background: #0a0a0f; color: #e4e4e7; font-family: 'Inter', system-ui, sans-serif;
    display: flex; justify-content: center; align-items: center; height: 100vh;
  }}
  .box {{
    background: #12121a; padding: 40px; border-radius: 10px; width: 360px;
    border: 1px solid #1e1e32;
  }}
  h1 {{ font-size: 20px; margin-bottom: 24px; color: #fff; text-align: center; }}
  .tabs {{ display: flex; margin-bottom: 24px; border-bottom: 1px solid #1e1e32; }}
  .tab {{
    flex: 1; padding: 10px; text-align: center; cursor: pointer;
    font-size: 14px; font-weight: 500; color: #71717a; transition: all 0.15s;
    border-bottom: 2px solid transparent;
  }}
  .tab.active {{ color: #60a5fa; border-bottom-color: #60a5fa; }}
  .tab:hover {{ color: #e4e4e7; }}
  .form {{ display: none; }}
  .form.active {{ display: block; }}
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
  .msg {{ font-size: 13px; margin-bottom: 12px; display: none; text-align: center; }}
  .msg.error {{ color: #ef4444; }}
  .msg.ok {{ color: #22c55e; }}
</style>
</head>
<body>
<div class="box">
  <h1>KVM Manager</h1>
  <div class="tabs">
    <div class="tab active" data-tab="login" onclick="switchTab('login')">Sign In</div>
    <div class="tab" data-tab="register" onclick="switchTab('register')">Register</div>
  </div>
  <div class="msg error" id="error"></div>
  <div class="msg ok" id="success"></div>
  <form id="login-form" class="form active">
    <label for="login-user">Email or Username</label>
    <input type="text" id="login-user" value="admin" autocomplete="username" placeholder="admin@localhost">
    <label for="login-pass">Password</label>
    <input type="password" id="login-pass" value="admin" autocomplete="current-password">
    <button type="submit">Sign In</button>
  </form>
  <form id="register-form" class="form">
    <label for="reg-user">Username</label>
    <input type="text" id="reg-user" placeholder="myuser" autocomplete="username" required>
    <label for="reg-email">Email <span style="color:#71717a">(optional)</span></label>
    <input type="email" id="reg-email" placeholder="user@example.com" autocomplete="email">
    <label for="reg-pass">Password</label>
    <input type="password" id="reg-pass" placeholder="min 8 chars" autocomplete="new-password" required>
    <button type="submit">Create Account</button>
  </form>
</div>
<script>
function switchTab(name) {{
  document.querySelectorAll('.tab, .form').forEach(el => el.classList.remove('active'));
  document.querySelector('.tab[data-tab="'+name+'"]').classList.add('active');
  document.getElementById(name+'-form').classList.add('active');
  document.getElementById('error').style.display = 'none';
  document.getElementById('success').style.display = 'none';
}}

document.getElementById('login-form').addEventListener('submit', async (e) => {{
  e.preventDefault();
  const username = document.getElementById('login-user').value;
  const password = document.getElementById('login-pass').value;
  const errEl = document.getElementById('error');
  errEl.style.display = 'none';
  try {{
    const resp = await fetch('/auth/login', {{
      method: 'POST',
      headers: {{ 'Content-Type': 'application/json' }},
      body: JSON.stringify({{ username, password }}),
    }});
    if (!resp.ok) {{ errEl.textContent = 'Invalid credentials'; errEl.style.display = 'block'; return; }}
    const data = await resp.json();
    localStorage.setItem('token', data.access_token);
    const params = new URLSearchParams(location.search);
    window.location.href = params.get('redirect') || '/';
  }} catch(e) {{
    errEl.textContent = 'Connection error';
    errEl.style.display = 'block';
  }}
}});

document.getElementById('register-form').addEventListener('submit', async (e) => {{
  e.preventDefault();
  const username = document.getElementById('reg-user').value;
  const email = document.getElementById('reg-email').value;
  const password = document.getElementById('reg-pass').value;
  const errEl = document.getElementById('error');
  const okEl = document.getElementById('success');
  errEl.style.display = 'none';
  okEl.style.display = 'none';
  try {{
    const resp = await fetch('/auth/register', {{
      method: 'POST',
      headers: {{ 'Content-Type': 'application/json' }},
      body: JSON.stringify({{ username, email: email || null, password }}),
    }});
    if (!resp.ok) {{ const d = await resp.json(); errEl.textContent = d.detail || 'Registration failed'; errEl.style.display = 'block'; return; }}
    const data = await resp.json();
    localStorage.setItem('token', data.access_token);
    okEl.textContent = 'Account created!';
    okEl.style.display = 'block';
    setTimeout(() => window.location.href = '/', 500);
  }} catch(e) {{
    errEl.textContent = 'Connection error';
    errEl.style.display = 'block';
  }}
}});
</script>
</body>
</html>"""
