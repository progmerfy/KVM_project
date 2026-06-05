import logging
import os
import time

from fastapi import Depends, FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware

from app.api import vm_routes, image_routes, host_routes, auth_routes
from app.config import settings
from app.errors import AppError
from app.auth import require_auth

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

logger = logging.getLogger(__name__)


class RequestLogMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start = time.monotonic()
        response = await call_next(request)
        elapsed = time.monotonic() - start
        logger.info(
            "%s %s -> %s (%.3fs)",
            request.method,
            request.url.path,
            response.status_code,
            elapsed,
        )
        response.headers["X-Request-Time-Ms"] = str(round(elapsed * 1000))
        return response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        return response


app = FastAPI(
    title="KVM Manager API",
    version="0.4.0",
    description=(
        "Pre-production KVM/libvirt VM management API. "
        "Create VMs with cloud-init SSH access, manage OS images, "
        "monitor host resources."
    ),
)

app.add_middleware(RequestLogMiddleware)
app.add_middleware(SecurityHeadersMiddleware)


@app.exception_handler(AppError)
async def app_error_handler(request: Request, exc: AppError):
    return JSONResponse(
        status_code=exc.http_status,
        content={"detail": {"code": exc.code, "message": exc.message}},
    )


@app.exception_handler(Exception)
async def unhandled_error_handler(request: Request, exc: Exception):
    logger.exception("Unhandled error: %s", exc)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal Server Error"},
    )


@app.get("/health")
def health_check():
    return {"status": "ok"}


@app.get("/health/secured")
def health_secured(auth: dict = Depends(require_auth)):
    return {"status": "ok", "user": auth.get("sub")}


@app.get("/", response_class=HTMLResponse)
def index():
    return HTMLResponse(content=_INDEX_HTML)


_INDEX_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>KVM Manager</title>
<style>
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body {
    background: #0f0f23; color: #e0e0e0; font-family: system-ui, monospace;
    display: flex; justify-content: center; align-items: center; height: 100vh;
  }
  .box { background: #1a1a2e; padding: 40px; border-radius: 8px; text-align: center; }
  h1 { font-size: 24px; margin-bottom: 8px; }
  p { color: #888; margin-bottom: 24px; font-size: 14px; }
  .links { display: flex; flex-direction: column; gap: 8px; }
  a { color: #4fc3f7; text-decoration: none; font-size: 14px; padding: 8px; border-radius: 4px; }
  a:hover { background: #16213e; }
  .status { margin-top: 20px; font-size: 12px; color: #555; }
  .status.ok { color: #2ecc71; }
</style>
</head>
<body>
<div class="box">
  <h1>KVM Manager</h1>
  <p>Virtual Machine Management API</p>
  <div class="links" id="links">
    <a href="/auth/login-page">Sign In</a>
  </div>
  <div class="status" id="status">Loading...</div>
</div>
<script>
const token = localStorage.getItem('token');
const linksEl = document.getElementById('links');
const statusEl = document.getElementById('status');
if (token) {
  fetch('/health/secured', { headers: { 'Authorization': 'Bearer ' + token } })
    .then(r => r.ok ? r.json() : Promise.reject())
    .then(d => {
      linksEl.innerHTML = '<a href="/vm/list">VM List</a><a href="/auth/login-page">Account</a>';
      statusEl.textContent = 'Authenticated as ' + d.user;
      statusEl.className = 'status ok';
    })
    .catch(() => {
      localStorage.removeItem('token');
      linksEl.innerHTML = '<a href="/auth/login-page">Sign In</a>';
      statusEl.textContent = 'Not authenticated';
    });
} else {
  statusEl.textContent = 'Not authenticated';
}
</script>
</body>
</html>"""


static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.isdir(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

app.include_router(auth_routes.router, prefix="/auth")
app.include_router(vm_routes.router, prefix="/vm")
app.include_router(image_routes.router, prefix="/images")
app.include_router(host_routes.router, prefix="/host")

if __name__ == "__main__":
    import uvicorn

    ssl_keyfile = os.getenv("SSL_KEY_FILE")
    ssl_certfile = os.getenv("SSL_CERT_FILE")
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=False,
        ssl_keyfile=ssl_keyfile,
        ssl_certfile=ssl_certfile,
    )
