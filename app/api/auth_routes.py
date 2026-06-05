import os
import secrets
import logging
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import HTMLResponse
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


@router.get("/login-page", response_class=HTMLResponse)
def login_page(redirect: str = "/"):
    return HTMLResponse(content=_LOGIN_PAGE_HTML.format(redirect=redirect))


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


_LOGIN_PAGE_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>KVM Manager - Login</title>
<style>
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{
    background: #0f0f23; color: #e0e0e0; font-family: system-ui, monospace;
    display: flex; justify-content: center; align-items: center; height: 100vh;
  }}
  .login-box {{
    background: #1a1a2e; padding: 40px; border-radius: 8px;
    box-shadow: 0 4px 24px rgba(0,0,0,0.5); width: 360px;
  }}
  h1 {{ font-size: 20px; margin-bottom: 24px; color: #fff; text-align: center; }}
  label {{ display: block; margin-bottom: 6px; font-size: 13px; color: #aaa; }}
  input {{
    width: 100%; padding: 10px 12px; margin-bottom: 16px;
    background: #16213e; border: 1px solid #2a2a4a; border-radius: 4px;
    color: #fff; font-size: 14px; font-family: monospace;
  }}
  input:focus {{ outline: none; border-color: #4fc3f7; }}
  button {{
    width: 100%; padding: 10px; background: #4fc3f7; color: #000;
    border: none; border-radius: 4px; font-size: 14px; font-weight: 600;
    cursor: pointer; font-family: monospace;
  }}
  button:hover {{ background: #29b6f6; }}
  .error {{ color: #e74c3c; font-size: 13px; margin-bottom: 12px; display: none; text-align: center; }}
  .info {{ color: #888; font-size: 12px; text-align: center; margin-top: 16px; }}
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
  <div class="info">Default: admin / admin</div>
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
