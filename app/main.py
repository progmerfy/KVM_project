import logging
import os
import threading
import time
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware

from app.api import vm_routes, image_routes, host_routes, auth_routes, audit_routes
from app.config import settings
from app.errors import AppError
from app.auth import require_auth
from app.database import init_db, get_enabled_backup_schedules, update_backup_schedule_last_run
from app.services.vm_manager import backup_vm


_scheduler_thread: threading.Thread | None = None
_scheduler_stop = threading.Event()


def _backup_scheduler_loop():
    logger.info("Backup scheduler started")
    while not _scheduler_stop.is_set():
        try:
            from croniter import croniter
            from datetime import datetime

            now = datetime.now()
            schedules = get_enabled_backup_schedules()
            for sched in schedules:
                try:
                    cron = croniter(sched["cron_expression"], now)
                    prev = cron.get_prev(datetime)
                    if (now - prev).total_seconds() < 90:
                        logger.info("Running scheduled backup for %s", sched["vm_name"])
                        backup_vm(sched["vm_name"])
                        update_backup_schedule_last_run(sched["id"])
                except Exception as e:
                    logger.error("Scheduled backup failed for %s: %s", sched["vm_name"], e)
        except Exception as e:
            logger.error("Backup scheduler error: %s", e)
        _scheduler_stop.wait(60)

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


@asynccontextmanager
async def lifespan(app: FastAPI):
    # startup
    init_db()
    logger.info("Database initialized")
    global _scheduler_thread
    _scheduler_thread = threading.Thread(target=_backup_scheduler_loop, daemon=True)
    _scheduler_thread.start()
    logger.info("Backup scheduler thread started")
    yield
    # shutdown
    _scheduler_stop.set()
    if _scheduler_thread:
        _scheduler_thread.join(timeout=5)
    logger.info("Backup scheduler stopped")


app = FastAPI(
    title="KVM Manager API",
    version="0.5.0",
    description=(
        "Pre-production KVM/libvirt VM management API. "
        "Create VMs with cloud-init SSH access, manage OS images, "
        "monitor host resources."
    ),
    lifespan=lifespan,
)

app.add_middleware(RequestLogMiddleware)
app.add_middleware(SecurityHeadersMiddleware)


@app.exception_handler(AppError)
async def app_error_handler(request: Request, exc: AppError):
    detail = {"code": exc.code, "message": exc.message}
    if exc.details:
        detail["details"] = exc.details
    if exc.runbook_url:
        detail["runbook_url"] = exc.runbook_url
    return JSONResponse(status_code=exc.http_status, content={"detail": detail})


@app.exception_handler(Exception)
async def unhandled_error_handler(request: Request, exc: Exception):
    logger.exception("Unhandled error: %s", exc)
    return JSONResponse(
        status_code=500,
        content={"detail": {"code": "INTERNAL_ERROR", "message": "Internal Server Error", "runbook_url": "https://docs.kvm-mgr.local/runbooks/infrastructure/internal-error"}},
    )


@app.get("/health")
def health_check():
    return {"status": "ok"}


@app.get("/health/secured")
def health_secured(auth: dict = Depends(require_auth)):
    return {"status": "ok", "user": auth.get("sub")}


@app.get("/", response_class=HTMLResponse)
def index():
    react_index = os.path.join(os.path.dirname(__file__), "static", "index.html")
    if os.path.exists(react_index):
        return HTMLResponse(content=open(react_index, encoding="utf-8").read())
    return HTMLResponse(content=_APP_HTML)


_APP_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>KVM Manager</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&display=swap" rel="stylesheet">
<style>
  :root {
    --bg: #0a0a0f;
    --surface: #12121a;
    --surface2: #1a1a2e;
    --border: #1e1e32;
    --text: #e4e4e7;
    --text2: #71717a;
    --accent: #60a5fa;
    --green: #22c55e;
    --red: #ef4444;
    --yellow: #eab308;
  }
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body {
    background: var(--bg); color: var(--text);
    font-family: 'Inter', system-ui, sans-serif;
    min-height: 100vh;
  }
  .layout { display: flex; min-height: 100vh; flex-direction: column; }
  .topbar {
    display: flex; align-items: center; justify-content: space-between;
    height: 48px; padding: 0 24px; background: var(--surface);
    border-bottom: 1px solid var(--border); flex-shrink: 0;
  }
  .topbar .breadcrumbs { display: flex; align-items: center; gap: 8px; font-size: 13px; color: var(--text2); }
  .topbar .breadcrumbs span { color: var(--text); font-weight: 500; }
  .topbar .breadcrumbs a { color: var(--text2); text-decoration: none; }
  .topbar .breadcrumbs a:hover { color: var(--text); }
  .topbar .user-menu { display: flex; align-items: center; gap: 12px; font-size: 13px; }
  .topbar .user-menu .avatar {
    width: 28px; height: 28px; border-radius: 50%; background: var(--accent);
    color: #000; display: flex; align-items: center; justify-content: center;
    font-weight: 600; font-size: 12px;
  }
  .topbar .user-menu .email { color: var(--text2); }
  .topbar .user-menu .logout {
    color: var(--text2); cursor: pointer; text-decoration: none; font-size: 12px;
    padding: 4px 10px; border-radius: 6px; border: 1px solid var(--border);
    transition: all 0.15s; display: inline-flex; align-items: center; gap: 4px;
  }
  .topbar .user-menu .logout:hover {
    color: var(--red); border-color: var(--red); background: rgba(239,68,68,0.1);
  }
  .body-wrap { display: flex; flex: 1; }
  .sidebar {
    width: 220px; background: var(--surface);
    border-right: 1px solid var(--border);
    padding: 24px 16px; flex-shrink: 0;
  }
  .sidebar .logo { font-size: 18px; font-weight: 600; margin-bottom: 32px; display: flex; align-items: center; gap: 8px; }
  .sidebar .logo svg { width: 24px; height: 24px; color: var(--accent); }
  .sidebar nav { display: flex; flex-direction: column; gap: 4px; }
  .sidebar nav a {
    color: var(--text2); text-decoration: none; padding: 10px 12px;
    border-radius: 6px; font-size: 14px; font-weight: 500;
    transition: all 0.15s; display: flex; align-items: center; gap: 10px;
  }
  .sidebar nav a:hover, .sidebar nav a.active { background: var(--surface2); color: var(--text); }
  .sidebar nav a svg { width: 18px; height: 18px; flex-shrink: 0; }
  .submenu {
    overflow: hidden; max-height: 0; transition: max-height 0.25s ease;
    display: flex; flex-direction: column;
  }
  .submenu.open { max-height: 100px; }
  .submenu a {
    padding: 8px 12px 8px 44px; font-size: 13px; color: #71717a; text-decoration: none;
    border-radius: 6px; transition: all 0.15s;
  }
  .submenu a:hover { color: #e4e4e7; background: var(--surface2); }
  .chevron.rotated { transform: rotate(180deg); }
  .sidebar .user { margin-top: auto; padding-top: 24px; border-top: 1px solid var(--border); font-size: 13px; color: var(--text2); }
  .main { flex: 1; padding: 32px 40px; max-width: 1200px; }
  .main h1 { font-size: 24px; font-weight: 600; margin-bottom: 4px; }
  .main p.sub { color: var(--text2); font-size: 14px; margin-bottom: 24px; }
  .stats { display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px; margin-bottom: 32px; }
  .stat-card {
    background: var(--surface); border: 1px solid var(--border);
    border-radius: 10px; padding: 20px;
  }
  .stat-card .label { font-size: 13px; color: var(--text2); margin-bottom: 4px; }
  .stat-card .value { font-size: 28px; font-weight: 600; }
  .stat-card .value.green { color: var(--green); }
  .stat-card .value.red { color: var(--red); }
  .vm-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(320px, 1fr)); gap: 16px; }
  .vm-card {
    background: var(--surface); border: 1px solid var(--border);
    border-radius: 10px; padding: 20px; cursor: pointer;
    transition: all 0.15s;
  }
  .vm-card:hover { border-color: var(--accent); transform: translateY(-1px); box-shadow: 0 4px 20px rgba(0,0,0,0.3); }
  .vm-card .top { display: flex; justify-content: space-between; align-items: start; margin-bottom: 12px; }
  .vm-card .name { font-size: 16px; font-weight: 600; }
  .vm-card .status-badge {
    font-size: 12px; font-weight: 500; padding: 3px 10px;
    border-radius: 20px; display: flex; align-items: center; gap: 6px;
  }
  .vm-card .status-badge .dot {
    width: 7px; height: 7px; border-radius: 50%; display: inline-block;
  }
  .vm-card .status-badge.running { background: rgba(34,197,94,0.12); color: var(--green); }
  .vm-card .status-badge.running .dot { background: var(--green); box-shadow: 0 0 6px var(--green); }
  .vm-card .status-badge.stopped { background: rgba(239,68,68,0.12); color: var(--red); }
  .vm-card .status-badge.stopped .dot { background: var(--red); }
  .vm-card .info { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; }
  .vm-card .info-item { font-size: 13px; color: var(--text2); }
  .vm-card .info-item span { color: var(--text); font-weight: 500; }
  .empty {
    text-align: center; padding: 60px 20px; color: var(--text2); grid-column: 1 / -1;
  }
  .empty svg { width: 48px; height: 48px; margin-bottom: 16px; opacity: 0.3; }
  .loading { text-align: center; padding: 60px; color: var(--text2); grid-column: 1 / -1; }
  @keyframes spin { to { transform: rotate(360deg); } }
  .spinner { width: 20px; height: 20px; border: 2px solid var(--border); border-top-color: var(--accent); border-radius: 50%; animation: spin 0.6s linear infinite; display: inline-block; }
  .btn {
    display: inline-flex; align-items: center; gap: 6px; padding: 8px 16px;
    border-radius: 6px; font-size: 13px; font-weight: 500; cursor: pointer;
    border: none; font-family: inherit; transition: all 0.15s;
  }
  .btn-primary { background: var(--accent); color: #000; }
  .btn-primary:hover { opacity: 0.9; }
  .btn-ghost { background: transparent; color: var(--text2); border: 1px solid var(--border); }
  .btn-ghost:hover { border-color: var(--text2); color: var(--text); }
  .actions { display: flex; gap: 8px; margin-top: 12px; flex-wrap: wrap; }
  .detail-header { margin-bottom: 24px; }
  .detail-header .back { color: var(--text2); text-decoration: none; font-size: 14px; display: inline-flex; align-items: center; gap: 4px; margin-bottom: 12px; }
  .detail-header .back:hover { color: var(--text); }
  .detail-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
  .detail-section {
    background: var(--surface); border: 1px solid var(--border);
    border-radius: 10px; padding: 20px;
  }
  .detail-section h3 { font-size: 14px; font-weight: 600; margin-bottom: 16px; color: var(--text2); text-transform: uppercase; letter-spacing: 0.5px; }
  .detail-section .row { display: flex; justify-content: space-between; padding: 8px 0; border-bottom: 1px solid var(--border); font-size: 14px; }
  .detail-section .row:last-child { border-bottom: none; }
  .detail-section .row .label { color: var(--text2); }
  .detail-section .row .value { font-weight: 500; }
  @media (max-width: 768px) {
    .sidebar { display: none; }
    .main { padding: 20px; }
    .stats { grid-template-columns: 1fr; }
    .vm-grid { grid-template-columns: 1fr; }
    .detail-grid { grid-template-columns: 1fr; }
    .topbar .user-menu .email { display: none; }
  }
  .create-form { max-width: 520px; }
  .create-form label { display: block; margin-bottom: 6px; font-size: 13px; color: #71717a; }
  .create-form label .opt { color: #52525b; font-style: italic; }
  .create-form input, .create-form select, .create-form textarea {
    width: 100%; padding: 10px 12px; margin-bottom: 16px;
    background: #0a0a0f; border: 1px solid #1e1e32; border-radius: 6px;
    color: #fff; font-size: 14px; font-family: inherit;
  }
  .create-form select { cursor: pointer; }
  .create-form select option { background: #12121a; }
  .create-form textarea { resize: vertical; }
  .create-form input:focus, .create-form select:focus, .create-form textarea:focus { outline: none; border-color: #60a5fa; }
  .create-form .form-row { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 12px; }
  @media (max-width: 480px) { .create-form .form-row { grid-template-columns: 1fr; } }
  .modal-overlay {
    display: none; position: fixed; inset: 0; z-index: 999;
    background: rgba(0,0,0,0.6); backdrop-filter: blur(4px);
    justify-content: center; align-items: center;
  }
  .modal-overlay.open { display: flex; }
  .modal {
    background: #12121a; border: 1px solid #1e1e32; border-radius: 12px;
    padding: 32px; width: 480px; max-width: 94vw; max-height: 90vh; overflow-y: auto;
  }
  .modal h2 { font-size: 18px; margin-bottom: 20px; }
  .modal .close { float: right; cursor: pointer; color: #71717a; font-size: 20px; }
  .modal .close:hover { color: #fff; }
  .confirm-btns { display: flex; gap: 8px; margin-top: 20px; }
  .confirm-btns .btn { flex: 1; justify-content: center; padding: 10px; }
  .skeleton { background: linear-gradient(90deg, var(--surface) 25%, var(--surface2) 50%, var(--surface) 75%); background-size: 200% 100%; animation: shimmer 1.2s ease-in-out infinite; border-radius: 8px; }
  @keyframes shimmer { 0% { background-position: 200% 0; } 100% { background-position: -200% 0; } }
  .sk-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(320px, 1fr)); gap: 16px; }
  .sk-card { height: 140px; }
  .sk-widget { height: 100px; }
  .tabs { display: flex; gap: 0; margin-bottom: 24px; border-bottom: 1px solid var(--border); }
  .tabs .tab {
    padding: 10px 20px; font-size: 13px; font-weight: 500; cursor: pointer;
    color: var(--text2); border-bottom: 2px solid transparent; transition: all 0.15s;
  }
  .tabs .tab:hover { color: var(--text); }
  .tabs .tab.active { color: var(--accent); border-bottom-color: var(--accent); }
  .tab-content { display: none; }
  .tab-content.active { display: block; }
  .activity-list { display: flex; flex-direction: column; gap: 8px; }
  .activity-item {
    display: flex; align-items: center; gap: 10px; padding: 10px 12px;
    background: var(--surface); border: 1px solid var(--border); border-radius: 8px; font-size: 13px;
  }
  .activity-item .act-icon { width: 28px; height: 28px; border-radius: 6px; display: flex; align-items: center; justify-content: center; flex-shrink: 0; font-size: 14px; }
  .activity-item .act-icon.create { background: rgba(34,197,94,0.15); color: var(--green); }
  .activity-item .act-icon.stop { background: rgba(239,68,68,0.15); color: var(--red); }
  .activity-item .act-icon.start { background: rgba(96,165,250,0.15); color: var(--accent); }
  .activity-item .act-icon.delete { background: rgba(239,68,68,0.15); color: var(--red); }
  .activity-item .act-text { flex: 1; }
  .activity-item .act-text .act-name { font-weight: 500; }
  .activity-item .act-text .act-time { font-size: 11px; color: var(--text2); margin-top: 2px; }
  .net-section { margin-bottom: 32px; }
  .net-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
  .leases-table { width: 100%; border-collapse: collapse; font-size: 13px; }
  .leases-table th { color: var(--text2); padding: 8px 6px; text-align: left; border-bottom: 1px solid var(--border); font-weight: 500; }
  .leases-table td { padding: 8px 6px; border-bottom: 1px solid var(--border); font-family: monospace; font-size: 12px; }
  .leases-table tr:last-child td { border-bottom: none; }
  .btn.loading { opacity: 0.6; pointer-events: none; position: relative; }
  .btn.loading::after {
    content: ''; width: 14px; height: 14px; border: 2px solid transparent;
    border-top-color: currentColor; border-radius: 50%; animation: spin 0.5s linear infinite;
    display: inline-block; margin-left: 6px;
  }
</style>
</head>
<body>
<div class="layout">
  <div class="topbar">
    <div class="breadcrumbs" id="breadcrumbs"><a href="#" onclick="setHash('/');return loadVMs(event)">Dashboard</a></div>
    <div class="user-menu" id="user-menu">
      <span class="email" id="user-email">Loading...</span>
      <div class="avatar" id="user-avatar">U</div>
      <span class="sep" style="width:1px;height:20px;background:var(--border)"></span>
      <a href="#" class="logout" onclick="return logout()">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="width:14px;height:14px"><path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/><polyline points="16 17 21 12 16 7"/><line x1="21" y1="12" x2="9" y2="12"/></svg>
        Logout
      </a>
    </div>
  </div>
  <div class="body-wrap">
  <aside class="sidebar" id="sidebar">
    <div class="logo">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="2" y="3" width="20" height="14" rx="2"/><path d="M8 21h8"/><path d="M12 17v4"/></svg>
      KVM Manager
    </div>
    <nav>
      <a href="#" onclick="return toggleSubmenu(event)" class="active">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="2" y="2" width="20" height="8" rx="2"/><rect x="2" y="14" width="20" height="8" rx="2"/></svg>
        Virtual Machines
        <svg class="chevron" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="margin-left:auto;width:16px;height:16px;transition:transform 0.2s"><path d="m6 9 6 6 6-6"/></svg>
      </a>
      <div class="submenu" id="vm-submenu">
        <a href="#" onclick="setHash('/');return loadVMs(event)">List VMs</a>
        <a href="#" onclick="return showCreateDialog()">+ Create VM</a>
      </div>
      <a href="#" onclick="return toggleIsoSubmenu(event)">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/></svg>
        ISO Store
        <svg class="chevron" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="margin-left:auto;width:16px;height:16px;transition:transform 0.2s"><path d="m6 9 6 6 6-6"/></svg>
      </a>
      <div class="submenu" id="iso-submenu">
        <a href="#" onclick="setHash('/isos');return loadISOs(event)">Browse Images</a>
        <a href="#" onclick="setHash('/isos/repo');return loadRepoImages(event)">Repo Images</a>
        <a href="#" onclick="return showUploadIsoDialog()">Upload ISO</a>
        <a href="#" onclick="return showDownloadIsoDialog()">Download from URL</a>
      </div>
      <a href="#" onclick="setHash('/settings');return loadSettings(event)">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"/></svg>
        Settings
      </a>
      <a href="#" onclick="return logout()">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/><polyline points="16 17 21 12 16 7"/><line x1="21" y1="12" x2="9" y2="12"/></svg>
        Logout
      </a>
    </nav>
  </aside>
  <main class="main" id="main-content">
    <div style="text-align:center;padding:80px 0">
      <div class="spinner"></div>
    </div>
  </main>
</div>
</div>
<div id="toast" style="position:fixed;bottom:20px;left:50%;transform:translateX(-50%);background:var(--surface2);color:var(--text);padding:10px 20px;border-radius:8px;font-size:13px;z-index:1000;opacity:0;transition:opacity 0.2s;border:1px solid var(--border);pointer-events:none;"></div>
<div class="modal-overlay" id="modal-overlay" onclick="if(event.target===this)closeModal()">
  <div class="modal">
    <span class="close" onclick="closeModal()">&times;</span>
    <h2 id="modal-title">Modal</h2>
    <div id="modal-body"></div>
  </div>
</div>
<div class="modal-overlay" id="confirm-overlay" onclick="if(event.target===this)closeConfirm()">
  <div class="modal" style="width:380px">
    <span class="close" onclick="closeConfirm()">&times;</span>
    <h2 id="confirm-title">Confirm</h2>
    <p id="confirm-message" style="color:var(--text2);font-size:14px;margin-bottom:8px"></p>
    <div class="confirm-btns">
      <button class="btn btn-ghost" onclick="closeConfirm()">Cancel</button>
      <button class="btn btn-primary" id="confirm-btn" style="background:var(--red);color:#fff" onclick="closeConfirm()">Confirm</button>
    </div>
  </div>
</div>
<script>
const TOKEN = localStorage.getItem('token');
if (!TOKEN) { window.location.href = '/auth/login-page?redirect=/'; }

function api(path) {
  return fetch(path, { headers: { 'Authorization': 'Bearer ' + TOKEN } }).then(r => { if (!r.ok) throw Error(r.status); return r.json(); });
}

function showToast(msg) {
  const el = document.getElementById('toast');
  el.textContent = msg; el.style.opacity = '1';
  setTimeout(() => el.style.opacity = '0', 2500);
  return false;
}

function sidebarActive(idx) {
  document.querySelectorAll('.sidebar nav > a').forEach((a, i) => a.classList.toggle('active', i === idx));
}

function toggleSubmenu(e) {
  e.preventDefault();
  const parent = e.currentTarget;
  const sub = document.getElementById('vm-submenu');
  const chevron = parent.querySelector('.chevron');
  sub.classList.toggle('open');
  chevron.classList.toggle('rotated');
  if (sub.classList.contains('open') && !sub._loaded) {
    sub._loaded = true;
    loadVMs(e);
  }
  return false;
}

function openModal() { document.getElementById('modal-overlay').classList.add('open'); }
function closeModal() { document.getElementById('modal-overlay').classList.remove('open'); }
function openConfirm() { document.getElementById('confirm-overlay').classList.add('open'); }
function closeConfirm() { document.getElementById('confirm-overlay').classList.remove('open'); }

function confirmAction(msg, fn) {
  document.getElementById('confirm-title').textContent = 'Confirm';
  document.getElementById('confirm-message').textContent = msg;
  const btn = document.getElementById('confirm-btn');
  btn.onclick = function() { closeConfirm(); fn(); };
  openConfirm();
}

function logout() {
  localStorage.removeItem('token');
  window.location.href = '/auth/login-page';
  return false;
}

function setBreadcrumbs(...crumbs) {
  const el = document.getElementById('breadcrumbs');
  el.innerHTML = crumbs.map((c, i) => {
    if (i === crumbs.length - 1) return `<span>${c}</span>`;
    return `<a href="#" onclick="setHash('/');return loadVMs(event)">${c}</a> <span style="color:var(--text2)">/</span>`;
  }).join('');
}

function statusBadge(state) {
  const display = state === 'running' ? 'running' : 'stopped';
  return `<span class="status-badge ${display}"><span class="dot"></span>${display}</span>`;
}

function skeletonCards(n) {
  return `<div class="sk-grid">${Array(n).fill('<div class="sk-card skeleton"></div>').join('')}</div>`;
}

function skeletonWidgets(n) {
  return Array(n).fill('<div class="sk-widget skeleton"></div>').join('');
}

function vmCard(vm) {
  return `<div class="vm-card" onclick="setHash('/vm/${vm.name}');loadDetail('${vm.name}')">
    <div class="top">
      <div class="name">${vm.name}</div>
      ${statusBadge(vm.state)}
    </div>
    <div class="info">
      <div class="info-item">CPU <span>${vm.cpu || '-'}</span></div>
      <div class="info-item">RAM <span>${vm.memory_mb ? (vm.memory_mb + ' MB') : '-'}</span></div>
      <div class="info-item">IP <span>${vm.ip_address || '-'}</span></div>
    </div>
    <div class="actions" onclick="event.stopPropagation()">
      ${vm.state === 'running' ? `<button class="btn btn-ghost" onclick="vmAction('${vm.name}','stop',this)">Stop</button>` : `<button class="btn btn-primary" onclick="vmAction('${vm.name}','start',this)">Start</button>`}
      <button class="btn btn-ghost" onclick="window.location.href='/vm/vnc/console/${vm.name}'">Console</button>
    </div>
  </div>`;
}

function addActivity(name, action) {
  let log = JSON.parse(localStorage.getItem('activity_log') || '[]');
  log.unshift({ name, action, time: Date.now() });
  if (log.length > 20) log = log.slice(0, 20);
  localStorage.setItem('activity_log', JSON.stringify(log));
}

function renderActivity() {
  const log = JSON.parse(localStorage.getItem('activity_log') || '[]');
  const icons = { start: '▶', stop: '⏹', create: '＋', delete: '✕', reboot: '↻' };
  const labels = { start: 'Started', stop: 'Stopped', create: 'Created', delete: 'Deleted', reboot: 'Rebooted' };
  if (!log.length) return '<div class="empty" style="grid-column:1"><p>No recent activity</p></div>';
  return log.slice(0, 8).map(e => {
    const icon = icons[e.action] || '●';
    const label = labels[e.action] || e.action;
    const ago = Math.floor((Date.now() - e.time) / 60000);
    const timeStr = ago < 1 ? 'just now' : ago < 60 ? ago + 'm ago' : Math.floor(ago / 60) + 'h ago';
    return `<div class="activity-item">
      <div class="act-icon ${e.action}">${icon}</div>
      <div class="act-text"><div class="act-name">${label} ${e.name}</div><div class="act-time">${timeStr}</div></div>
    </div>`;
  }).join('');
}

function vmAction(name, action, btn) {
  if (action === 'stop' || action === 'delete') {
    const verb = action === 'stop' ? 'stop' : 'delete';
    confirmAction('Are you sure you want to ' + verb + ' VM "' + name + '"?', function() {
      doVmAction(name, action, btn);
    });
    return;
  }
  doVmAction(name, action, btn);
}

function doVmAction(name, action, btn) {
  if (btn) btn.classList.add('loading');
  addActivity(name, action);
  return fetch('/vm/' + action, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'Authorization': 'Bearer ' + TOKEN },
    body: JSON.stringify({ name }),
  }).then(r => { if (r.ok) { showToast(action + ' ' + name); loadVMs(); } else { r.json().then(d => showToast(d.detail?.message || 'Failed')); if (btn) btn.classList.remove('loading'); } }).catch(() => { showToast('Error'); if (btn) btn.classList.remove('loading'); });
}

function loadVMs(e) {
  if (e) e.preventDefault();
  setBreadcrumbs('Dashboard');
  const main = document.getElementById('main-content');
  main.innerHTML = `
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px">
      <h1>Dashboard</h1>
      <button class="btn btn-primary" onclick="showCreateDialog()">+ New VM</button>
    </div>
    <p class="sub"><span class="skeleton" style="display:inline-block;width:200px;height:16px">&nbsp;</span></p>
    <div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:16px;margin-bottom:32px">${skeletonWidgets(5)}</div>
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px"><h2 style="font-size:18px;font-weight:600">Virtual Machines</h2></div>
    ${skeletonCards(3)}`;
  Promise.all([
    api('/host/info').catch(() => ({})),
    api('/host/stats').catch(() => ({})),
    api('/images/storage/info').catch(() => ({})),
    api('/vm/list').catch(() => ({ vms: [] })),
    api('/host/networks').catch(() => ({ networks: [], leases: [] })),
  ]).then(([hostInfo, hostStats, imgStorage, vmData, netData]) => {
    const h = hostInfo.host || {};
    const s = hostStats.stats || {};
    const st = imgStorage.storage || {};
    const vms = vmData.vms || [];
    const nets = netData.networks || [];
    const leases = netData.leases || [];
    const running = vms.filter(v => v.state === 'running').length;
    const stopped = vms.filter(v => v.state === 'stopped').length;
    const cpu = s.cpu || {};
    const mem = s.memory || {};
    const disks = s.storage || [];
    const sysDisk = disks.find(d => d.mount === '/') || disks[0] || {};
    function netTable() {
      if (!nets.length) return '<div class="empty" style="grid-column:span 2"><p>No networks</p></div>';
      return nets.map(n => `
        <div style="display:flex;align-items:center;justify-content:space-between;padding:10px 14px;background:var(--surface);border:1px solid var(--border);border-radius:8px;font-size:13px">
          <div><span style="font-weight:500">${n.name}</span> <span style="color:var(--text2)">${n.bridge || ''}</span></div>
          <div><span style="color:${n.active ? 'var(--green)' : 'var(--red)'}">${n.active ? 'Active' : 'Inactive'}</span>${n.subnet ? ' &middot; ' + n.subnet : ''}</div>
        </div>`).join('');
    }
    function leaseTable() {
      if (!leases.length) return '<div class="empty"><p>No active DHCP leases</p></div>';
      return `<table style="width:100%;border-collapse:collapse;font-size:13px">
        <thead><tr style="color:var(--text2);border-bottom:1px solid var(--border)"><th style="padding:8px 6px;text-align:left">IP</th><th style="padding:8px 6px;text-align:left">MAC</th><th style="padding:8px 6px;text-align:left">Hostname</th><th style="padding:8px 6px;text-align:left">Network</th></tr></thead>
        <tbody>${leases.map(l => `<tr style="border-bottom:1px solid var(--border)"><td style="padding:8px 6px;font-family:monospace">${l.ip}</td><td style="padding:8px 6px;font-family:monospace;font-size:12px">${l.mac}</td><td style="padding:8px 6px">${l.hostname || '-'}</td><td style="padding:8px 6px">${l.network}</td></tr>`).join('')}</tbody>
      </table>`;
    }
    main.innerHTML = `
      <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px">
        <h1>Dashboard</h1>
        <button class="btn btn-primary" onclick="showCreateDialog()">+ New VM</button>
      </div>
      <p class="sub">${h.hostname || 'host'} &middot; ${h.cpu?.model || ''} &middot; ${h.cpu?.cores || '?'} cores${h.uptime ? ' &middot; Uptime: ' + h.uptime : ''}</p>

      <div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:16px;margin-bottom:32px">
        <div class="stat-card">
          <div class="label">CPU Usage</div>
          <div class="value" style="color:${cpu.used_percent > 80 ? 'var(--red)' : cpu.used_percent > 50 ? 'var(--yellow)' : 'var(--green)'}">${cpu.used_percent ?? '?'}%</div>
          <div style="margin-top:8px;height:6px;background:var(--border);border-radius:3px;overflow:hidden">
            <div style="height:100%;width:${cpu.used_percent || 0}%;background:${cpu.used_percent > 80 ? 'var(--red)' : cpu.used_percent > 50 ? 'var(--yellow)' : 'var(--green)'};border-radius:3px;transition:width 0.3s"></div>
          </div>
        </div>

        <div class="stat-card">
          <div class="label">Memory</div>
          <div class="value" style="color:${mem.used_percent > 80 ? 'var(--red)' : mem.used_percent > 50 ? 'var(--yellow)' : 'var(--green)'}">${mem.used_percent ?? '?'}%</div>
          <div style="font-size:12px;color:var(--text2);margin-top:2px">${mem.used_mb || 0} / ${mem.total_mb || 0} MB</div>
          <div style="margin-top:8px;height:6px;background:var(--border);border-radius:3px;overflow:hidden">
            <div style="height:100%;width:${mem.used_percent || 0}%;background:${mem.used_percent > 80 ? 'var(--red)' : mem.used_percent > 50 ? 'var(--yellow)' : 'var(--green)'};border-radius:3px;transition:width 0.3s"></div>
          </div>
        </div>

        <div class="stat-card">
          <div class="label">System Disk (${sysDisk.mount || '/'})</div>
          <div class="value" style="color:${sysDisk.used_percent > 80 ? 'var(--red)' : sysDisk.used_percent > 50 ? 'var(--yellow)' : 'var(--green)'}">${sysDisk.used_percent ?? '?'}%</div>
          <div style="font-size:12px;color:var(--text2);margin-top:2px">${sysDisk.used_gb || 0} / ${sysDisk.size_gb || 0} GB</div>
          <div style="margin-top:8px;height:6px;background:var(--border);border-radius:3px;overflow:hidden">
            <div style="height:100%;width:${sysDisk.used_percent || 0}%;background:${sysDisk.used_percent > 80 ? 'var(--red)' : sysDisk.used_percent > 50 ? 'var(--yellow)' : 'var(--green)'};border-radius:3px;transition:width 0.3s"></div>
          </div>
        </div>

        <div class="stat-card">
          <div class="label">Image Storage</div>
          <div class="value">${st.free_gb ?? '?'} GB</div>
          <div style="font-size:12px;color:var(--text2);margin-top:2px">${st.used_gb || 0} / ${st.total_gb || 0} GB free</div>
          <div style="margin-top:8px;height:6px;background:var(--border);border-radius:3px;overflow:hidden">
            <div style="height:100%;width:${st.total_gb ? ((st.total_gb - st.free_gb) / st.total_gb * 100) : 0}%;background:var(--accent);border-radius:3px;transition:width 0.3s"></div>
          </div>
        </div>

        <div class="stat-card">
          <div class="label">Virtual Machines</div>
          <div class="value">${vms.length}</div>
          <div style="display:flex;gap:12px;margin-top:6px;font-size:13px">
            <span style="color:var(--green)">${running} running</span>
            <span style="color:var(--red)">${stopped} stopped</span>
          </div>
        </div>
      </div>

      <div style="display:grid;grid-template-columns:2fr 1fr;gap:24px;margin-bottom:32px">
        <div>
          <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px">
            <h2 style="font-size:18px;font-weight:600">Virtual Machines</h2>
            <input type="text" id="vm-search" placeholder="Search VMs..." oninput="filterVMs(this.value)" style="padding:8px 12px;background:var(--surface);border:1px solid var(--border);border-radius:6px;color:var(--text);font-size:13px;font-family:inherit;width:200px">
          </div>
          <div class="vm-grid" id="vm-grid">${vms.length ? vms.map(vmCard).join('') : '<div class="empty"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><rect x="2" y="3" width="20" height="14" rx="2"/><path d="M8 21h8"/><path d="M12 17v4"/></svg><p>No virtual machines yet</p></div>'}</div>
        </div>
        <div>
          <h2 style="font-size:16px;font-weight:600;margin-bottom:12px">Recent Activity</h2>
          <div class="activity-list">${renderActivity()}</div>
        </div>
      </div>

      <div style="margin-bottom:32px">
        <h2 style="font-size:18px;font-weight:600;margin-bottom:12px">Network Interfaces</h2>
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-bottom:24px">
          <div class="detail-section">
            <h3>Networks</h3>
            <div style="display:flex;flex-direction:column;gap:6px">${netTable()}</div>
          </div>
          <div class="detail-section">
            <h3>DHCP Leases (${leases.length})</h3>
            ${leaseTable()}
          </div>
        </div>
      </div>`;
  }).catch(() => { main.innerHTML = '<div style="text-align:center;padding:60px;color:var(--red)">Failed to load. Check your connection.</div>'; });
  return false;
}

function filterVMs(q) {
  const grid = document.getElementById('vm-grid');
  if (!grid) return;
  const cards = grid.querySelectorAll('.vm-card');
  cards.forEach(c => {
    const name = c.querySelector('.name')?.textContent || '';
    c.style.display = name.toLowerCase().includes(q.toLowerCase()) ? '' : 'none';
  });
}

let _detailTab = 'config';

function loadDetail(name, initialTab) {
  const main = document.getElementById('main-content');
  setBreadcrumbs('Dashboard', name);
  main.innerHTML = `
    <div class="detail-header">
      <h1>${name}</h1>
      <p class="sub" id="detail-sub"></p>
    </div>
    <div class="actions" id="detail-actions" style="margin-bottom:24px"></div>
    <div class="tabs">
      <div class="tab ${initialTab === 'config' || !initialTab ? 'active' : ''}" data-tab="config" onclick="setHash('/vm/${name}/tab/config');switchDetailTab('config', '${name}')">Config</div>
      <div class="tab ${initialTab === 'snapshots' ? 'active' : ''}" data-tab="snapshots" onclick="setHash('/vm/${name}/tab/snapshots');switchDetailTab('snapshots', '${name}')">Snapshots</div>
      <div class="tab ${initialTab === 'backups' ? 'active' : ''}" data-tab="backups" onclick="setHash('/vm/${name}/tab/backups');switchDetailTab('backups', '${name}')">Backups</div>
      <div class="tab ${initialTab === 'metrics' ? 'active' : ''}" data-tab="metrics" onclick="setHash('/vm/${name}/tab/metrics');switchDetailTab('metrics', '${name}')">Metrics</div>
    </div>
    <div id="detail-body"><div style="text-align:center;padding:40px"><div class="spinner"></div></div></div>`;
  switchDetailTab(initialTab || 'config', name);
}

function loadDetailActions(name) {
  api('/vm/info/' + name).then(info => {
    const vm = info.vm || {};
    const uptime = vm.uptime_seconds;
    const uptimeStr = uptime ? Math.floor(uptime / 3600) + 'h ' + Math.floor((uptime % 3600) / 60) + 'm' : '-';
    document.getElementById('detail-sub').innerHTML = statusBadge(vm.state) + (uptime ? ' &middot; Uptime: ' + uptimeStr : '');
    document.getElementById('detail-actions').innerHTML = (vm.state === 'running' ? `<button class="btn btn-ghost" onclick="vmAction('${vm.name}','stop')">Stop</button><button class="btn btn-ghost" onclick="vmAction('${vm.name}','reboot')">Reboot</button>` : `<button class="btn btn-primary" onclick="vmAction('${vm.name}','start')">Start</button>`) + `<button class="btn btn-primary" onclick="window.location.href='/vm/vnc/console/${vm.name}'">Console</button>`;
  }).catch(() => {});
}

function switchDetailTab(tab, name) {
  _detailTab = tab;
  document.querySelectorAll('.tabs .tab').forEach(t => t.classList.toggle('active', t.dataset.tab === tab));
  const body = document.getElementById('detail-body');
  loadDetailActions(name);
  if (tab === 'config') loadDetailConfig(name, body);
  else if (tab === 'snapshots') loadDetailSnapshots(name, body);
  else if (tab === 'backups') loadDetailBackups(name, body);
  else if (tab === 'metrics') loadDetailMetrics(name, body);
}

function loadDetailConfig(name, body) {
  Promise.all([api('/vm/info/' + name), api('/vm/metrics/' + name).catch(() => ({}))]).then(([info, metrics]) => {
    const vm = info.vm || {};
    const m = metrics.metrics || {};
    const memStats = m.memory_stats || {};
    const disks = vm.disks || [];
    const nets = vm.interfaces || [];
    body.innerHTML = `
      <div class="detail-grid">
        <div class="detail-section">
          <h3>Configuration</h3>
          <div class="row"><span class="label">vCPUs</span><span class="value">${vm.cpu || '-'}</span></div>
          <div class="row"><span class="label">Memory</span><span class="value">${vm.memory_mb || '-'} MB</span></div>
          <div class="row"><span class="label">IP Address</span><span class="value">${vm.ip_address || '-'}</span></div>
          <div class="row"><span class="label">OS Type</span><span class="value">${vm.os_type || '-'}</span></div>
          <div class="row"><span class="label">UUID</span><span class="value" style="font-size:11px;font-family:monospace">${vm.uuid || '-'}</span></div>
          <div class="row"><span class="label">VNC Port</span><span class="value">${vm.vnc_port || '-'}</span></div>
          <div class="row" style="display:flex;justify-content:space-between;align-items:center">
            <span class="label">Auto Start</span>
            <label style="position:relative;display:inline-block;width:36px;height:20px;cursor:pointer">
              <input type="checkbox" ${vm.autostart ? 'checked' : ''} onchange="toggleAutostart('${vm.name}', this.checked)" style="opacity:0;width:0;height:0">
              <span style="position:absolute;inset:0;background:${vm.autostart ? 'var(--accent)' : 'var(--border)'};border-radius:10px;transition:0.2s">
                <span style="position:absolute;top:2px;left:${vm.autostart ? '18px' : '2px'};width:16px;height:16px;background:#fff;border-radius:50%;transition:0.2s"></span>
              </span>
            </label>
          </div>
        </div>
        <div class="detail-section">
          <h3>Performance</h3>
          <div class="row"><span class="label">CPU Time</span><span class="value">${m.cpu_time_s || '-'} s</span></div>
          <div class="row"><span class="label">Max Memory</span><span class="value">${m.max_memory_mb || vm.max_memory_mb || '-'} MB</span></div>
          <div class="row"><span class="label">Memory (host)</span><span class="value">${m.memory_mb || '-'} MB</span></div>
          ${memStats.available ? `<div class="row"><span class="label">Mem Available</span><span class="value">${memStats.available} MB</span></div>` : ''}
          ${memStats.unused ? `<div class="row"><span class="label">Mem Unused</span><span class="value">${memStats.unused} MB</span></div>` : ''}
        </div>
      </div>
      ${disks.length ? `<div class="detail-section" style="margin-top:16px">
        <h3>Storage (${disks.length} device${disks.length > 1 ? 's' : ''})</h3>
        ${disks.map(d => `
          <div style="display:flex;align-items:center;justify-content:space-between;padding:10px 0;border-bottom:1px solid var(--border);font-size:14px">
            <div><span style="font-weight:500">${d.target || '?'}</span> <span style="color:var(--text2);font-size:12px">${d.device || ''}${d.readonly ? ' (ro)' : ''}</span></div>
            <div style="text-align:right;font-size:12px;color:var(--text2);max-width:300px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${d.source || '-'}</div>
          </div>`).join('')}
      </div>` : ''}
      ${nets.length ? `<div class="detail-section" style="margin-top:16px">
        <h3>Network Interfaces (${nets.length})</h3>
        ${nets.map(n => `
          <div style="display:flex;align-items:center;justify-content:space-between;padding:10px 0;border-bottom:1px solid var(--border);font-size:14px">
            <div><span style="font-weight:500;font-family:monospace;font-size:13px">${n.mac || '?'}</span></div>
            <div><span style="color:var(--text2);font-size:13px">${n.source || ''}${n.model ? ' (' + n.model + ')' : ''}</span></div>
          </div>`).join('')}
      </div>` : ''}
      <div style="display:flex;gap:8px;margin-top:24px">
        <button class="btn btn-ghost" onclick="vmAction('${name}','delete')" style="color:var(--red);border-color:var(--red)">Delete VM</button>
        <button class="btn btn-ghost" onclick="showCloneDialog('${name}')">Clone</button>
      </div>`;
  }).catch(() => { body.innerHTML = '<div style="text-align:center;padding:60px;color:var(--red)">Failed to load</div>'; });
}

function toggleAutostart(name, enable) {
  fetch('/vm/autostart?name=' + encodeURIComponent(name) + '&enable=' + enable, {
    method: 'POST', headers: { 'Authorization': 'Bearer ' + TOKEN },
  }).then(r => { if (r.ok) showToast('Autostart ' + (enable ? 'enabled' : 'disabled')); });
}

function showCloneDialog(name) {
  document.getElementById('modal-title').textContent = 'Clone VM';
  document.getElementById('modal-body').innerHTML = `
    <form onsubmit="return doClone(event, '${name}')">
      <label style="display:block;margin-bottom:4px;font-size:13px;color:#71717a">New VM Name</label>
      <input type="text" id="clone-name" placeholder="${name}-clone" required autofocus style="width:100%;padding:10px 12px;margin-bottom:14px;background:#0a0a0f;border:1px solid #1e1e32;border-radius:6px;color:#fff;font-size:14px;font-family:inherit">
      <div style="display:flex;gap:8px;margin-top:8px">
        <button type="submit" class="btn btn-primary" style="flex:1">Clone</button>
        <button type="button" class="btn btn-ghost" onclick="closeModal()" style="flex:1">Cancel</button>
      </div>
    </form>`;
  openModal();
}

function doClone(e, name) {
  e.preventDefault();
  const newName = document.getElementById('clone-name').value;
  closeModal();
  fetch('/vm/clone', {
    method: 'POST', headers: { 'Content-Type': 'application/json', 'Authorization': 'Bearer ' + TOKEN },
    body: JSON.stringify({ name, new_name: newName }),
  }).then(r => r.json().then(d => ({ ok: r.ok, data: d }))).then(({ ok, data }) => {
    if (!ok) { showToast(data.detail?.message || 'Clone failed'); return; }
    showToast('Cloned as ' + newName);
    loadVMs();
  }).catch(() => showToast('Error'));
  return false;
}

function loadDetailSnapshots(name, body) {
  body.innerHTML = '<div style="text-align:center;padding:40px"><div class="spinner"></div></div>';
  api('/vm/snapshot/list/' + name).then(data => {
    const snaps = data.snapshots || [];
    body.innerHTML = `
      <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:16px">
        <h3 style="font-size:16px;font-weight:600">Snapshots</h3>
        <button class="btn btn-primary" onclick="createSnapshot('${name}',this)">+ Create Snapshot</button>
      </div>
      ${snaps.length ? `<div style="display:grid;gap:8px">${snaps.map(s => `
        <div style="display:flex;align-items:center;justify-content:space-between;background:var(--surface);border:1px solid var(--border);border-radius:8px;padding:12px 16px">
          <span style="font-weight:500">${s.name}</span>
          <div style="display:flex;gap:6px">
            <button class="btn btn-ghost" onclick="revertSnapshot('${name}','${s.name}')">Revert</button>
            <button class="btn btn-ghost" onclick="deleteSnapshot('${name}','${s.name}')">Delete</button>
          </div>
        </div>`).join('')}</div>` : '<div class="empty"><p>No snapshots</p></div>'}`;
  }).catch(() => { body.innerHTML = '<div style="text-align:center;padding:60px;color:var(--red)">Failed to load snapshots</div>'; });
}

function loadDetailBackups(name, body) {
  body.innerHTML = '<div style="text-align:center;padding:40px"><div class="spinner"></div></div>';
  api('/vm/backup/list/' + name).then(data => {
    const backups = data.backups || [];
    body.innerHTML = `
      <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:16px">
        <h3 style="font-size:16px;font-weight:600">Backups</h3>
        <button class="btn btn-primary" onclick="createBackup('${name}',this)">+ Backup Now</button>
      </div>
      ${backups.length ? `<div style="display:grid;gap:8px">${backups.map(b => `
        <div style="display:flex;align-items:center;justify-content:space-between;background:var(--surface);border:1px solid var(--border);border-radius:8px;padding:12px 16px">
          <span style="font-weight:500">${b.dir}</span>
          <span style="font-size:12px;color:var(--text2)">${b.timestamp}</span>
          <button class="btn btn-ghost" onclick="deleteBackup('${name}','${b.dir}')" style="font-size:12px;padding:4px 10px;color:var(--red);border-color:var(--red)">Delete</button>
        </div>`).join('')}</div>` : '<div class="empty"><p>No backups yet</p></div>'}`;
  }).catch(() => { body.innerHTML = '<div style="text-align:center;padding:60px;color:var(--red)">Failed to load backups</div>'; });
}

function loadDetailMetrics(name, body) {
  body.innerHTML = '<div style="text-align:center;padding:40px"><div class="spinner"></div></div>';
  api('/vm/metrics/' + name).then(data => {
    const m = data.metrics || {};
    body.innerHTML = `
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:16px">
        <div class="detail-section">
          <h3>CPU</h3>
          <div class="row"><span class="label">Count</span><span class="value">${m.cpu_count || '-'}</span></div>
          <div class="row"><span class="label">Time</span><span class="value">${m.cpu_time_s || '-'} s</span></div>
        </div>
        <div class="detail-section">
          <h3>Memory</h3>
          <div class="row"><span class="label">Max</span><span class="value">${m.max_memory_mb || '-'} MB</span></div>
          <div class="row"><span class="label">Current</span><span class="value">${m.memory_mb || '-'} MB</span></div>
          ${(m.memory_stats || {}).available ? `<div class="row"><span class="label">Available</span><span class="value">${m.memory_stats.available} MB</span></div>` : ''}
        </div>
      </div>
      ${Object.keys(m.block_stats || {}).length ? `
        <h3 style="font-size:14px;font-weight:600;margin:20px 0 12px;color:var(--text2);text-transform:uppercase;letter-spacing:0.5px">Block Devices</h3>
        <div style="display:grid;gap:8px">${Object.entries(m.block_stats).map(([dev, s]) => `
          <div style="background:var(--surface);border:1px solid var(--border);border-radius:8px;padding:12px 16px">
            <div style="font-weight:500;margin-bottom:6px">${dev}</div>
            <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;font-size:13px;color:var(--text2)">
              <span>Read: ${(s.rd_bytes / 1e6).toFixed(1)} MB</span>
              <span>Write: ${(s.wr_bytes / 1e6).toFixed(1)} MB</span>
              <span>Read req: ${s.rd_req}</span>
              <span>Write req: ${s.wr_req}</span>
            </div>
          </div>`).join('')}</div>` : ''}
      <div style="margin-top:16px">
        <h3 style="font-size:14px;font-weight:600;margin-bottom:12px;color:var(--text2);text-transform:uppercase;letter-spacing:0.5px">State</h3>
        <div style="background:var(--surface);border:1px solid var(--border);border-radius:8px;padding:12px 16px;font-size:13px">
          ${m.state || 'unknown'}
        </div>
      </div>`;
  }).catch(() => { body.innerHTML = '<div style="text-align:center;padding:60px;color:var(--red)">Failed to load metrics</div>'; });
}

function createSnapshot(name, btn) {
  document.getElementById('modal-title').textContent = 'Create Snapshot';
  document.getElementById('modal-body').innerHTML = `
    <form id="snap-form" onsubmit="return doCreateSnapshot(event,'${name}')">
      <label style="display:block;margin-bottom:4px;font-size:13px;color:#71717a">Snapshot Name</label>
      <input type="text" id="snap-name" placeholder="my-snapshot" required autofocus style="width:100%;padding:10px 12px;margin-bottom:14px;background:#0a0a0f;border:1px solid #1e1e32;border-radius:6px;color:#fff;font-size:14px;font-family:inherit">
      <div style="display:flex;gap:8px;margin-top:8px">
        <button type="submit" class="btn btn-primary" style="flex:1">Create</button>
        <button type="button" class="btn btn-ghost" onclick="closeModal()" style="flex:1">Cancel</button>
      </div>
    </form>`;
  openModal();
}

function doCreateSnapshot(e, name) {
  e.preventDefault();
  const snap = document.getElementById('snap-name').value;
  if (!snap) return false;
  closeModal();
  fetch('/vm/snapshot/create?name=' + encodeURIComponent(name) + '&snap_name=' + encodeURIComponent(snap), {
    method: 'POST', headers: { 'Authorization': 'Bearer ' + TOKEN },
  }).then(r => { if (r.ok) { showToast('Snapshot created'); loadDetail(name, 'snapshots'); } else showToast('Failed'); }).catch(() => showToast('Error'));
  return false;
}

function revertSnapshot(name, snap) {
  confirmAction('Revert to snapshot "' + snap + '"?', function() {
    fetch('/vm/snapshot/revert?name=' + encodeURIComponent(name) + '&snap_name=' + encodeURIComponent(snap), {
      method: 'POST', headers: { 'Authorization': 'Bearer ' + TOKEN },
    }).then(r => { if (r.ok) { showToast('Reverted to ' + snap); loadDetail(name, 'snapshots'); } else showToast('Failed'); }).catch(() => showToast('Error'));
  });
}

function deleteSnapshot(name, snap) {
  confirmAction('Delete snapshot "' + snap + '"?', function() {
    fetch('/vm/snapshot/delete?name=' + encodeURIComponent(name) + '&snap_name=' + encodeURIComponent(snap), {
      method: 'DELETE', headers: { 'Authorization': 'Bearer ' + TOKEN },
    }).then(r => {
      if (r.ok) { showToast('Deleted'); return loadDetail(name, 'snapshots'); }
      showToast('Failed');
    }).catch(() => showToast('Error'));
  });
}

function createBackup(name, btn) {
  if (btn) btn.classList.add('loading');
  fetch('/vm/backup', {
    method: 'POST', headers: { 'Content-Type': 'application/json', 'Authorization': 'Bearer ' + TOKEN },
    body: JSON.stringify({ name }),
  }).then(r => { if (r.ok) { showToast('Backup created'); loadDetail(name, 'backups'); } else { showToast('Failed'); if (btn) btn.classList.remove('loading'); } }).catch(() => { showToast('Error'); if (btn) btn.classList.remove('loading'); });
}

function deleteBackup(name, dir) {
  confirmAction('Delete backup at "' + dir + '"?', function() {
    fetch('/vm/backup/delete?backup_dir=' + encodeURIComponent(dir), {
      method: 'DELETE', headers: { 'Authorization': 'Bearer ' + TOKEN },
    }).then(r => { if (r.ok) { showToast('Backup deleted'); loadDetail(name, 'backups'); } else showToast('Failed'); });
  });
}

function uploadIso() {
  const fileInput = document.getElementById('iso-file');
  const file = fileInput.files[0];
  if (!file) { showToast('Select a file'); return; }
  const fd = new FormData();
  fd.append('file', file);
  if (document.getElementById('iso-upload-name').value) fd.append('name', document.getElementById('iso-upload-name').value);
  closeModal();
  fetch('/images/upload', {
    method: 'POST',
    headers: { 'Authorization': 'Bearer ' + TOKEN },
    body: fd,
  }).then(r => r.json().then(d => ({ ok: r.ok, data: d }))).then(({ ok, data }) => {
    if (!ok) { showToast(data.detail?.message || 'Upload failed'); return; }
    showToast('ISO uploaded');
    loadISOs();
  }).catch(() => showToast('Upload error'));
}

function downloadIso() {
  const url = document.getElementById('iso-url').value;
  if (!url) { showToast('Enter a URL'); return; }
  const name = document.getElementById('iso-dl-name').value;
  const fd = new FormData();
  fd.append('url', url);
  if (name) fd.append('name', name);
  closeModal();
  fetch('/images/download', {
    method: 'POST',
    headers: { 'Authorization': 'Bearer ' + TOKEN },
    body: fd,
  }).then(r => r.json().then(d => ({ ok: r.ok, data: d }))).then(({ ok, data }) => {
    if (!ok) { showToast(data.detail?.message || 'Download failed'); return; }
    showToast('ISO downloaded');
    loadISOs();
  }).catch(() => showToast('Download error'));
}

function deleteIso(name) {
  confirmAction('Delete image "' + name + '"?', function() {
    fetch('/images/' + encodeURIComponent(name), {
      method: 'DELETE',
      headers: { 'Authorization': 'Bearer ' + TOKEN },
    }).then(r => { if (r.ok) { showToast(name + ' deleted'); loadISOs(); } else { showToast('Delete failed'); } }).catch(() => showToast('Error'));
  });
}

function toggleIsoSubmenu(e) {
  e.preventDefault();
  const parent = e.currentTarget;
  const sub = document.getElementById('iso-submenu');
  const chevron = parent.querySelector('.chevron');
  sub.classList.toggle('open');
  chevron.classList.toggle('rotated');
  return false;
}

function loadISOs(e) {
  if (e) e.preventDefault();
  const main = document.getElementById('main-content');
  setBreadcrumbs('ISO Store', 'Browse Images');
  main.innerHTML = `
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px">
      <h1>Images</h1>
      <div style="display:flex;gap:8px">
        <button class="btn btn-ghost" onclick="showDownloadIsoDialog()">Download from URL</button>
        <button class="btn btn-primary" onclick="showUploadIsoDialog()">Upload ISO</button>
      </div>
    </div>
    <p class="sub"><span class="skeleton" style="display:inline-block;width:180px;height:16px">&nbsp;</span></p>
    ${skeletonCards(3)}`;
  api('/images/list').then(data => {
    const imgs = data.images || [];
    const isos = imgs.filter(i => i.name.toLowerCase().endsWith('.iso'));
    const disks = imgs.filter(i => !i.name.toLowerCase().endsWith('.iso'));
    main.innerHTML = `
      <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px">
        <h1>Images</h1>
        <div style="display:flex;gap:8px">
          <button class="btn btn-ghost" onclick="showDownloadIsoDialog()">Download from URL</button>
          <button class="btn btn-primary" onclick="showUploadIsoDialog()">Upload ISO</button>
        </div>
      </div>
      <p class="sub">${isos.length} ISO${isos.length !== 1 ? 's' : ''}, ${disks.length} disk image${disks.length !== 1 ? 's' : ''}</p>
      <div class="vm-grid">
        ${isos.length ? isos.map(isoCard).join('') : '<div class="empty"><p>No ISOs yet. Upload or download one.</p></div>'}
      </div>
      ${disks.length ? `<h2 style="font-size:16px;margin:24px 0 12px">Disk Images</h2><div class="vm-grid">${disks.map(isoCard).join('')}</div>` : ''}`;
  }).catch(() => { main.innerHTML = '<div style="text-align:center;padding:60px;color:var(--red)">Failed to load</div>'; });
  return false;
}

function loadRepoImages(e) {
  if (e) e.preventDefault();
  const main = document.getElementById('main-content');
  setBreadcrumbs('ISO Store', 'Repo Images');
  main.innerHTML = '<div style="text-align:center;padding:80px 0"><div class="spinner"></div></div>';
  const famLabels = { debian: 'Debian-like (Debian, Ubuntu)', rhel: 'RHEL-like (Fedora, CentOS, Rocky, Alma)', arch: 'Arch-like (Arch Linux)' };
  api('/images/repo/list').then(data => {
    const families = data.families || {};
    let html = `
      <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px">
        <h1>Repository Images</h1>
      </div>
      <p class="sub">Click an image to download it to local storage</p>`;
    for (const [fam, imgs] of Object.entries(families)) {
      html += `<h2 style="font-size:16px;margin:20px 0 12px">${famLabels[fam] || fam}</h2><div class="vm-grid">`;
      html += imgs.map(img => `
        <div class="vm-card" style="cursor:pointer" onclick="downloadRepoImage('${img.name}',this)">
          <div class="top"><div class="name">${img.name}</div></div>
          <div class="info"><div class="info-item" style="grid-column:span 2">${img.description}</div></div>
          <div class="actions" onclick="event.stopPropagation()">
            <button class="btn btn-primary" onclick="downloadRepoImage('${img.name}',this)">Download</button>
          </div>
        </div>`).join('');
      html += `</div>`;
    }
    if (!Object.keys(families).length) html += '<div class="empty"><p>No repository images available</p></div>';
    main.innerHTML = html;
  }).catch(() => { main.innerHTML = '<div style="text-align:center;padding:60px;color:var(--red)">Failed to load repos</div>'; });
  return false;
}

function downloadRepoImage(name, btn) {
  if (btn) btn.classList.add('loading');
  fetch('/images/download-cloud?name=' + encodeURIComponent(name), {
    method: 'POST',
    headers: { 'Authorization': 'Bearer ' + TOKEN },
  }).then(r => r.json().then(d => ({ ok: r.ok, data: d }))).then(({ ok, data }) => {
    if (!ok) { showToast(data.detail?.message || 'Download failed'); }
    else { showToast(name + ' downloaded'); }
    if (btn) btn.classList.remove('loading');
  }).catch(() => { showToast('Download error'); if (btn) btn.classList.remove('loading'); });
}

function isoCard(img) {
  const isIso = img.name.toLowerCase().endsWith('.iso');
  const size = img.actual_size_bytes ? (img.actual_size_bytes / (1024*1024)).toFixed(1) + ' MB' : img.virtual_size_gb + ' GB';
  return `<div class="vm-card">
    <div class="top">
      <div class="name">${img.name}</div>
    </div>
    <div class="info">
      <div class="info-item">Size <span>${size}</span></div>
      <div class="info-item">Format <span>${img.format || '-'}</span></div>
    </div>
    <div class="actions" onclick="event.stopPropagation()">
      <button class="btn btn-ghost" onclick="deleteIso('${img.name}')">Delete</button>
    </div>
  </div>`;
}

function showUploadIsoDialog() {
  document.getElementById('modal-title').textContent = 'Upload ISO';
  document.getElementById('modal-body').innerHTML = `
    <form onsubmit="uploadIso();return false">
      <label style="display:block;margin-bottom:4px;font-size:13px;color:#71717a">File</label>
      <input type="file" id="iso-file" autofocus style="width:100%;padding:10px 12px;margin-bottom:14px;background:#0a0a0f;border:1px solid #1e1e32;border-radius:6px;color:#fff;font-size:14px;font-family:inherit">
      <label style="display:block;margin-bottom:4px;font-size:13px;color:#71717a">Name <span style="color:#52525b">(optional, defaults to filename)</span></label>
      <input type="text" id="iso-upload-name" placeholder="my-image.iso" style="width:100%;padding:10px 12px;margin-bottom:14px;background:#0a0a0f;border:1px solid #1e1e32;border-radius:6px;color:#fff;font-size:14px;font-family:inherit">
      <div style="display:flex;gap:8px;margin-top:8px">
        <button type="submit" class="btn btn-primary" style="flex:1">Upload</button>
        <button type="button" class="btn btn-ghost" onclick="closeModal()" style="flex:1">Cancel</button>
      </div>
    </form>`;
  openModal();
  return false;
}

function showDownloadIsoDialog() {
  document.getElementById('modal-title').textContent = 'Download ISO from URL';
  document.getElementById('modal-body').innerHTML = `
    <form onsubmit="downloadIso();return false">
      <label style="display:block;margin-bottom:4px;font-size:13px;color:#71717a">URL</label>
      <input type="url" id="iso-url" placeholder="https://releases.ubuntu.com/ubuntu.iso" required autofocus style="width:100%;padding:10px 12px;margin-bottom:14px;background:#0a0a0f;border:1px solid #1e1e32;border-radius:6px;color:#fff;font-size:14px;font-family:inherit">
      <label style="display:block;margin-bottom:4px;font-size:13px;color:#71717a">Name <span style="color:#52525b">(optional, defaults from URL)</span></label>
      <input type="text" id="iso-dl-name" placeholder="my-image.iso" style="width:100%;padding:10px 12px;margin-bottom:14px;background:#0a0a0f;border:1px solid #1e1e32;border-radius:6px;color:#fff;font-size:14px;font-family:inherit">
      <div style="display:flex;gap:8px;margin-top:8px">
        <button type="submit" class="btn btn-primary" style="flex:1">Download</button>
        <button type="button" class="btn btn-ghost" onclick="closeModal()" style="flex:1">Cancel</button>
      </div>
    </form>`;
  openModal();
  return false;
}

function showCreateDialog() {
  setBreadcrumbs('Dashboard', 'Create VM');
  api('/images/list').then(images => {
    const imgs = images.images || [];
    const opts = imgs.length ? imgs.map(i => `<option value="${i.path}">${i.name || i.path}</option>`).join('') : '<option value="">No images available</option>';
    document.getElementById('modal-title').textContent = 'Create VM';
    document.getElementById('modal-body').innerHTML = `
      <form id="create-vm-form" onsubmit="return createVM(event)">
        <label style="display:block;margin-bottom:4px;font-size:13px;color:#71717a">Name</label>
        <input type="text" id="vm-name" placeholder="my-vm" required autofocus style="width:100%;padding:10px 12px;margin-bottom:14px;background:#0a0a0f;border:1px solid #1e1e32;border-radius:6px;color:#fff;font-size:14px;font-family:inherit">

        <label style="display:block;margin-bottom:4px;font-size:13px;color:#71717a">Base Image <span style="color:#52525b">(optional, blank disk if empty)</span></label>
        <select id="vm-image" style="width:100%;padding:10px 12px;margin-bottom:14px;background:#0a0a0f;border:1px solid #1e1e32;border-radius:6px;color:#fff;font-size:14px;font-family:inherit"><option value="">None (blank disk)</option>${opts}</select>

        <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:10px">
          <div><label style="display:block;margin-bottom:4px;font-size:13px;color:#71717a">CPU</label><input type="number" id="vm-cpu" value="1" min="1" style="width:100%;padding:10px 12px;margin-bottom:14px;background:#0a0a0f;border:1px solid #1e1e32;border-radius:6px;color:#fff;font-size:14px;font-family:inherit"></div>
          <div><label style="display:block;margin-bottom:4px;font-size:13px;color:#71717a">RAM (MB)</label><input type="number" id="vm-ram" value="512" min="128" step="128" style="width:100%;padding:10px 12px;margin-bottom:14px;background:#0a0a0f;border:1px solid #1e1e32;border-radius:6px;color:#fff;font-size:14px;font-family:inherit"></div>
          <div><label style="display:block;margin-bottom:4px;font-size:13px;color:#71717a">Disk (GB)</label><input type="number" id="vm-disk" value="10" min="1" style="width:100%;padding:10px 12px;margin-bottom:14px;background:#0a0a0f;border:1px solid #1e1e32;border-radius:6px;color:#fff;font-size:14px;font-family:inherit"></div>
        </div>

        <label style="display:block;margin-bottom:4px;font-size:13px;color:#71717a">ISO <span style="color:#52525b">(optional)</span></label>
        <input type="text" id="vm-iso" placeholder="/iso/ubuntu.iso" style="width:100%;padding:10px 12px;margin-bottom:14px;background:#0a0a0f;border:1px solid #1e1e32;border-radius:6px;color:#fff;font-size:14px;font-family:inherit">

        <label style="display:block;margin-bottom:4px;font-size:13px;color:#71717a">SSH Key <span style="color:#52525b">(optional)</span></label>
        <textarea id="vm-ssh" placeholder="ssh-rsa AAAAB3..." rows="2" style="width:100%;padding:10px 12px;margin-bottom:14px;background:#0a0a0f;border:1px solid #1e1e32;border-radius:6px;color:#fff;font-size:14px;font-family:inherit;resize:vertical"></textarea>

        <div style="display:flex;gap:8px;margin-top:8px">
          <button type="submit" class="btn btn-primary" style="flex:1">Create</button>
          <button type="button" class="btn btn-ghost" onclick="closeModal()" style="flex:1">Cancel</button>
        </div>
      </form>`;
    openModal();
  }).catch(() => showToast('Failed to load images'));
}

function createVM(e) {
  e.preventDefault();
  const image = document.getElementById('vm-image').value;
  const body = {
    name: document.getElementById('vm-name').value,
    cpu: parseInt(document.getElementById('vm-cpu').value) || 1,
    memory_mb: parseInt(document.getElementById('vm-ram').value) || 512,
    disk_gb: parseInt(document.getElementById('vm-disk').value) || 10,
  };
  if (image) body.image = image;
  const iso = document.getElementById('vm-iso').value;
  if (iso) body.iso_path = iso;
  const ssh = document.getElementById('vm-ssh').value;
  if (ssh) body.cloud_init_ssh_key = ssh;
  closeModal();
  addActivity(body.name, 'create');
  fetch('/vm/create', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'Authorization': 'Bearer ' + TOKEN },
    body: JSON.stringify(body),
  }).then(r => r.json().then(d => ({ ok: r.ok, data: d }))).then(({ ok, data }) => {
    if (!ok) { showToast(data.detail?.message || 'Failed'); return; }
    showToast('VM ' + body.name + ' created');
    loadVMs();
  }).catch(() => showToast('Error'));
  return false;
}

function loadSettings(e) {
  if (e) e.preventDefault();
  setBreadcrumbs('Settings');
  const main = document.getElementById('main-content');
  api('/auth/me').then(d => {
    const user = d.user || {};
    const isAdmin = user.is_admin;
    let adminSections = '';
    if (isAdmin) {
      api('/auth/users').then(ud => {
        const users = ud.users || [];
        const list = document.getElementById('user-list');
        if (list) list.innerHTML = users.map(u => `
          <div style="display:flex;align-items:center;justify-content:space-between;padding:10px 14px;background:var(--surface);border:1px solid var(--border);border-radius:8px">
            <div><span style="font-weight:500">${u.username}</span> ${u.is_admin ? '<span style="font-size:11px;color:var(--accent);margin-left:6px">admin</span>' : ''}<div style="font-size:12px;color:var(--text2)">${u.email || ''}</div></div>
            <span style="font-size:12px;color:var(--text2)">${u.created_at || ''}</span>
          </div>`).join('');
      }).catch(() => {});
      api('/host/info').then(hi => {
        const el = document.getElementById('host-info');
        if (el) {
          const h = hi.host || {};
          const rows = [];
          rows.push(`<div class="row"><span class="label">Hostname</span><span class="value">${h.hostname || ''}</span></div>`);
          rows.push(`<div class="row"><span class="label">Uptime</span><span class="value">${h.uptime || ''}</span></div>`);
          if (h.cpu) {
            rows.push(`<div class="row"><span class="label">CPU Cores</span><span class="value">${h.cpu.cores || ''}</span></div>`);
            rows.push(`<div class="row"><span class="label">CPU Model</span><span class="value">${h.cpu.model || ''}</span></div>`);
          }
          if (h.memory) {
            rows.push(`<div class="row"><span class="label">Memory</span><span class="value">${h.memory.total_gb || ''} GB (${h.memory.total_mb || ''} MB)</span></div>`);
          }
          if (h.storage && h.storage.length) {
            h.storage.forEach(s => {
              rows.push(`<div class="row"><span class="label">Disk (${s.filesystem || ''})</span><span class="value">${s.size_gb || ''} GB total, ${s.used_gb || ''} GB used, ${s.avail_gb || ''} GB free</span></div>`);
            });
          }
          el.innerHTML = rows.join('');
        }
      }).catch(() => {});
      api('/images/storage/info').then(si => {
        const el = document.getElementById('storage-info');
        if (el && si.storage) {
          const s = si.storage;
          el.innerHTML = `
            <div class="row"><span class="label">Path</span><span class="value">${s.path || ''}</span></div>
            <div class="row"><span class="label">Total</span><span class="value">${s.total_gb || ''} GB</span></div>
            <div class="row"><span class="label">Used</span><span class="value">${s.used_gb || ''} GB</span></div>
            <div class="row"><span class="label">Free</span><span class="value">${s.free_gb || ''} GB</span></div>`;
        }
      }).catch(() => {});
      api('/vm/backup/schedules').then(sd => {
        const el = document.getElementById('schedule-list');
        if (el && sd.schedules) {
          el.innerHTML = sd.schedules.map(s => `
            <div style="display:flex;align-items:center;justify-content:space-between;padding:10px 14px;background:var(--surface);border:1px solid var(--border);border-radius:8px">
              <div>
                <span style="font-weight:500">${s.vm_name}</span>
                <span style="font-size:12px;color:var(--text2);margin-left:8px">cron: ${s.cron_expression}</span>
                <span style="font-size:12px;color:var(--text2);margin-left:8px">retention: ${s.retention}d</span>
                <span style="font-size:12px;margin-left:8px;color:${s.enabled ? 'var(--green)' : 'var(--red)'}">${s.enabled ? 'enabled' : 'disabled'}</span>
                ${s.last_run ? `<span style="font-size:11px;color:var(--text2);margin-left:8px">last: ${s.last_run}</span>` : ''}
              </div>
              <div style="display:flex;gap:6px">
                <button class="btn btn-ghost" onclick="editSchedule(${s.id},'${s.vm_name}','${s.cron_expression}',${s.retention},${s.enabled})" style="font-size:12px;padding:4px 10px">Edit</button>
                <button class="btn btn-ghost" onclick="deleteSchedule(${s.id})" style="font-size:12px;padding:4px 10px;color:var(--red);border-color:var(--red)">Delete</button>
              </div>
            </div>`).join('');
        }
      }).catch(() => {});
      adminSections = `
        <div class="detail-section" style="margin-top:24px">
          <h3>Users</h3>
          <div id="user-list"><div style="text-align:center;padding:12px"><div class="spinner"></div></div></div>
        </div>
        <div class="detail-section" style="margin-top:24px">
          <h3>Host Info</h3>
          <div id="host-info"><div style="text-align:center;padding:12px"><div class="spinner"></div></div></div>
        </div>
        <div class="detail-section" style="margin-top:24px">
          <h3>Storage</h3>
          <div id="storage-info"><div style="text-align:center;padding:12px"><div class="spinner"></div></div></div>
        </div>
        <div class="detail-section" style="margin-top:24px">
          <h3>Backup Schedules</h3>
          <div style="margin-bottom:10px">
            <button class="btn btn-primary" onclick="showAddScheduleDialog()" style="font-size:13px;padding:6px 14px">+ Add Schedule</button>
          </div>
          <div id="schedule-list"><div style="text-align:center;padding:12px"><div class="spinner"></div></div></div>
        </div>`;
    }
    main.innerHTML = `
      <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px">
        <h1>Settings</h1>
      </div>
      <p class="sub">${user.email || user.username}</p>

      <div class="detail-grid">
        <div class="detail-section">
          <h3>Change Password</h3>
          <form onsubmit="changePassword(event)" style="margin-top:8px">
            <label style="display:block;margin-bottom:4px;font-size:13px;color:#71717a">Current Password</label>
            <input type="password" id="cp-current" required style="width:100%;padding:10px 12px;margin-bottom:12px;background:#0a0a0f;border:1px solid #1e1e32;border-radius:6px;color:#fff;font-size:14px;font-family:inherit">
            <label style="display:block;margin-bottom:4px;font-size:13px;color:#71717a">New Password</label>
            <input type="password" id="cp-new" required minlength="8" style="width:100%;padding:10px 12px;margin-bottom:12px;background:#0a0a0f;border:1px solid #1e1e32;border-radius:6px;color:#fff;font-size:14px;font-family:inherit">
            <button type="submit" class="btn btn-primary" style="padding:10px 20px">Update Password</button>
          </form>
          <div id="cp-msg" style="font-size:13px;margin-top:8px;display:none"></div>
        </div>
        <div class="detail-section">
          <h3>Server Info</h3>
          <div class="row"><span class="label">Host</span><span class="value">${window.location.hostname}</span></div>
          <div class="row"><span class="label">API Version</span><span class="value">0.5.0</span></div>
          <div class="row"><span class="label">User</span><span class="value">${user.username}</span></div>
          <div class="row"><span class="label">Role</span><span class="value">${isAdmin ? 'Admin' : 'User'}</span></div>
        </div>
      </div>
      ${adminSections}`;
  }).catch(() => { main.innerHTML = '<div style="text-align:center;padding:60px;color:var(--red)">Failed to load</div>'; });
  return false;
}

function showAddScheduleDialog() {
  document.getElementById('modal-title').textContent = 'Add Backup Schedule';
  document.getElementById('modal-body').innerHTML = `
    <form onsubmit="saveSchedule(event)">
      <label style="display:block;margin-bottom:4px;font-size:13px;color:#71717a">VM Name</label>
      <input type="text" id="sched-vm" required placeholder="my-vm" autofocus style="width:100%;padding:10px 12px;margin-bottom:14px;background:#0a0a0f;border:1px solid #1e1e32;border-radius:6px;color:#fff;font-size:14px;font-family:inherit">
      <label style="display:block;margin-bottom:4px;font-size:13px;color:#71717a">Cron Expression</label>
      <input type="text" id="sched-cron" required placeholder="0 3 * * *" style="width:100%;padding:10px 12px;margin-bottom:14px;background:#0a0a0f;border:1px solid #1e1e32;border-radius:6px;color:#fff;font-size:14px;font-family:inherit">
      <div style="font-size:12px;color:var(--text2);margin-bottom:14px">Examples: <code>0 3 * * *</code> daily 3am, <code>*/30 * * * *</code> every 30min</div>
      <label style="display:block;margin-bottom:4px;font-size:13px;color:#71717a">Retention (days)</label>
      <input type="number" id="sched-retention" value="7" min="1" max="365" style="width:100%;padding:10px 12px;margin-bottom:14px;background:#0a0a0f;border:1px solid #1e1e32;border-radius:6px;color:#fff;font-size:14px;font-family:inherit">
      <input type="hidden" id="sched-id" value="">
      <div style="display:flex;gap:8px;margin-top:8px">
        <button type="submit" class="btn btn-primary" style="flex:1">Save</button>
        <button type="button" class="btn btn-ghost" onclick="closeModal()" style="flex:1">Cancel</button>
      </div>
    </form>`;
  openModal();
}

function editSchedule(id, vmName, cronExpr, retention, enabled) {
  document.getElementById('modal-title').textContent = 'Edit Backup Schedule';
  document.getElementById('modal-body').innerHTML = `
    <form onsubmit="updateSchedule(event, ${id})">
      <label style="display:block;margin-bottom:4px;font-size:13px;color:#71717a">VM Name</label>
      <input type="text" id="sched-vm" value="${vmName}" disabled style="width:100%;padding:10px 12px;margin-bottom:14px;background:#0a0a0f;border:1px solid #1e1e32;border-radius:6px;color:#71717a;font-size:14px;font-family:inherit">
      <label style="display:block;margin-bottom:4px;font-size:13px;color:#71717a">Cron Expression</label>
      <input type="text" id="sched-cron" value="${cronExpr}" required autofocus style="width:100%;padding:10px 12px;margin-bottom:14px;background:#0a0a0f;border:1px solid #1e1e32;border-radius:6px;color:#fff;font-size:14px;font-family:inherit">
      <label style="display:block;margin-bottom:4px;font-size:13px;color:#71717a">Retention (days)</label>
      <input type="number" id="sched-retention" value="${retention}" min="1" max="365" style="width:100%;padding:10px 12px;margin-bottom:14px;background:#0a0a0f;border:1px solid #1e1e32;border-radius:6px;color:#fff;font-size:14px;font-family:inherit">
      <label style="display:flex;align-items:center;gap:8px;font-size:13px;color:#71717a;margin-bottom:14px">
        <input type="checkbox" id="sched-enabled" ${enabled ? 'checked' : ''}> Enabled
      </label>
      <div style="display:flex;gap:8px;margin-top:8px">
        <button type="submit" class="btn btn-primary" style="flex:1">Update</button>
        <button type="button" class="btn btn-ghost" onclick="closeModal()" style="flex:1">Cancel</button>
      </div>
    </form>`;
  openModal();
}

function saveSchedule(e) {
  e.preventDefault();
  const vm = document.getElementById('sched-vm').value.trim();
  const cron = document.getElementById('sched-cron').value.trim();
  const retention = parseInt(document.getElementById('sched-retention').value) || 7;
  closeModal();
  fetch('/vm/backup/schedules', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'Authorization': 'Bearer ' + TOKEN },
    body: JSON.stringify({ vm_name: vm, cron_expression: cron, retention: retention }),
  }).then(r => r.json().then(d => ({ ok: r.ok, data: d }))).then(({ ok, data }) => {
    if (!ok) { showToast(data.detail?.message || 'Failed'); }
    else { showToast('Schedule created'); loadSettings(); }
  }).catch(() => showToast('Error'));
}

function updateSchedule(e, id) {
  e.preventDefault();
  const cron = document.getElementById('sched-cron').value.trim();
  const retention = parseInt(document.getElementById('sched-retention').value) || 7;
  const enabled = document.getElementById('sched-enabled').checked;
  closeModal();
  fetch('/vm/backup/schedules/' + id, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json', 'Authorization': 'Bearer ' + TOKEN },
    body: JSON.stringify({ cron_expression: cron, retention: retention, enabled: enabled }),
  }).then(r => r.json().then(d => ({ ok: r.ok, data: d }))).then(({ ok, data }) => {
    if (!ok) { showToast(data.detail?.message || 'Failed'); }
    else { showToast('Schedule updated'); loadSettings(); }
  }).catch(() => showToast('Error'));
}

function deleteSchedule(id) {
  confirmAction('Delete this backup schedule?', () => {
    fetch('/vm/backup/schedules/' + id, {
      method: 'DELETE',
      headers: { 'Authorization': 'Bearer ' + TOKEN },
    }).then(r => r.json().then(d => ({ ok: r.ok, data: d }))).then(({ ok }) => {
      if (ok) { showToast('Schedule deleted'); loadSettings(); }
      else { showToast('Failed'); }
    }).catch(() => showToast('Error'));
  });
}

function changePassword(e) {
  e.preventDefault();
  const current = document.getElementById('cp-current').value;
  const newPass = document.getElementById('cp-new').value;
  const msg = document.getElementById('cp-msg');
  fetch('/auth/change-password', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'Authorization': 'Bearer ' + TOKEN },
    body: JSON.stringify({ current_password: current, new_password: newPass }),
  }).then(r => r.json().then(d => ({ ok: r.ok, data: d }))).then(({ ok, data }) => {
    msg.style.display = 'block';
    if (ok) { msg.style.color = 'var(--green)'; msg.textContent = 'Password updated'; document.getElementById('cp-current').value = ''; document.getElementById('cp-new').value = ''; }
    else { msg.style.color = 'var(--red)'; msg.textContent = data.detail || 'Failed'; }
  }).catch(() => { msg.style.display = 'block'; msg.style.color = 'var(--red)'; msg.textContent = 'Error'; });
}

function navigate() {
  const hash = window.location.hash.slice(1) || '/';
  if (hash.startsWith('/vm/')) {
    const parts = hash.split('/');
    const name = parts[2];
    const tab = parts[4] || 'config';
    if (name) { loadDetail(name, tab); }
  } else if (hash === '/settings') {
    loadSettings();
  } else if (hash === '/isos') {
    loadISOs();
  } else if (hash === '/isos/repo') {
    loadRepoImages();
  } else {
    loadVMs();
  }
}

function setHash(h) {
  const url = window.location.pathname + window.location.search + '#' + h;
  if (window.location.hash.slice(1) !== h) {
    history.replaceState(null, '', url);
  }
}

function init() {
  api('/auth/me').then(d => {
    const user = d.user || {};
    document.getElementById('user-email').textContent = user.email || user.username || 'User';
    document.getElementById('user-avatar').textContent = (user.username || 'U')[0].toUpperCase();
    document.getElementById('vm-submenu').classList.add('open');
    document.querySelector('.chevron').classList.add('rotated');
    navigate();
    window.addEventListener('popstate', navigate);
  }).catch(() => { window.location.href = '/auth/login-page?redirect=/'; });
}
init();
</script>
</body>
</html>"""


static_dir = os.path.join(os.path.dirname(__file__), "static")
assets_dir = os.path.join(static_dir, "assets")
if os.path.isdir(assets_dir):
    app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

app.include_router(auth_routes.router, prefix="/auth")
app.include_router(vm_routes.router, prefix="/vm")
app.include_router(image_routes.router, prefix="/images")
app.include_router(host_routes.router, prefix="/host")
app.include_router(audit_routes.router, prefix="/audit")

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
