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
from app.database import init_db

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
    version="0.5.0",
    description=(
        "Pre-production KVM/libvirt VM management API. "
        "Create VMs with cloud-init SSH access, manage OS images, "
        "monitor host resources."
    ),
)


@app.on_event("startup")
def on_startup():
    init_db()
    logger.info("Database initialized")

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
  .layout { display: flex; min-height: 100vh; }
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
</style>
</head>
<body>
<div class="layout">
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
        <a href="#" onclick="return loadVMs(event)">List VMs</a>
        <a href="#" onclick="return showCreateDialog()">+ Create VM</a>
      </div>
      <a href="#" onclick="return toggleIsoSubmenu(event)">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/></svg>
        ISO Store
        <svg class="chevron" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="margin-left:auto;width:16px;height:16px;transition:transform 0.2s"><path d="m6 9 6 6 6-6"/></svg>
      </a>
      <div class="submenu" id="iso-submenu">
        <a href="#" onclick="return loadISOs(event)">Browse Images</a>
        <a href="#" onclick="return loadRepoImages(event)">Repo Images</a>
        <a href="#" onclick="return showUploadIsoDialog()">Upload ISO</a>
        <a href="#" onclick="return showDownloadIsoDialog()">Download from URL</a>
      </div>
      <a href="#" onclick="return showToast('Coming soon')">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"/></svg>
        Settings
      </a>
      <a href="#" onclick="return logout()" style="margin-top:8px">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/><polyline points="16 17 21 12 16 7"/><line x1="21" y1="12" x2="9" y2="12"/></svg>
        Logout
      </a>
    </nav>
    <div class="user" id="user-info">Not authenticated</div>
  </aside>
  <main class="main" id="main-content">
    <div style="text-align:center;padding:80px 0">
      <div class="spinner"></div>
    </div>
  </main>
</div>
<div id="toast" style="position:fixed;bottom:20px;left:50%;transform:translateX(-50%);background:var(--surface2);color:var(--text);padding:10px 20px;border-radius:8px;font-size:13px;z-index:1000;opacity:0;transition:opacity 0.2s;border:1px solid var(--border);pointer-events:none;"></div>
<div class="modal-overlay" id="modal-overlay" onclick="if(event.target===this)closeModal()">
  <div class="modal">
    <span class="close" onclick="closeModal()">&times;</span>
    <h2 id="modal-title">Create VM</h2>
    <div id="modal-body"></div>
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
  setTimeout(() => el.style.opacity = '0', 2000);
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

function logout() {
  localStorage.removeItem('token');
  window.location.href = '/auth/login-page';
  return false;
}

function statusBadge(state) {
  const cls = state === 'running' ? 'running' : 'stopped';
  return `<span class="status-badge ${cls}"><span class="dot"></span>${state}</span>`;
}

function vmCard(vm) {
  return `<div class="vm-card" onclick="loadDetail('${vm.name}')">
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
      ${vm.state === 'running' ? `<button class="btn btn-ghost" onclick="vmAction('${vm.name}','stop')">Stop</button>` : `<button class="btn btn-primary" onclick="vmAction('${vm.name}','start')">Start</button>`}
      <button class="btn btn-ghost" onclick="window.location.href='/vm/vnc/console/${vm.name}'">Console</button>
    </div>
  </div>`;
}

function vmAction(name, action) {
  return fetch('/vm/' + action, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'Authorization': 'Bearer ' + TOKEN },
    body: JSON.stringify({ name }),
  }).then(r => { if (r.ok) { showToast(action + ' ' + name); loadVMs(); } else { showToast('Failed: ' + action); } }).catch(() => showToast('Error'));
}

function loadVMs(e) {
  if (e) e.preventDefault();
  const main = document.getElementById('main-content');
  main.innerHTML = '<div style="text-align:center;padding:80px 0"><div class="spinner"></div></div>';
  Promise.all([
    api('/host/info').catch(() => ({})),
    api('/host/stats').catch(() => ({})),
    api('/images/storage/info').catch(() => ({})),
    api('/vm/list').catch(() => ({ vms: [] })),
  ]).then(([hostInfo, hostStats, imgStorage, vmData]) => {
    const h = hostInfo.host || {};
    const s = hostStats.stats || {};
    const st = imgStorage.storage || {};
    const vms = vmData.vms || [];
    const running = vms.filter(v => v.state === 'running').length;
    const stopped = vms.filter(v => v.state === 'stopped').length;
    const cpu = s.cpu || {};
    const mem = s.memory || {};
    const disks = s.storage || [];
    const sysDisk = disks.find(d => d.mount === '/') || disks[0] || {};
    main.innerHTML = `
      <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px">
        <h1>Dashboard</h1>
        <button class="btn btn-primary" onclick="showCreateDialog()">+ New VM</button>
      </div>
      <p class="sub">${h.hostname || 'host'} &middot; ${h.cpu?.model || ''} &middot; ${h.cpu?.cores || '?'} cores</p>

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

      <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px">
        <h2 style="font-size:18px;font-weight:600">Virtual Machines</h2>
      </div>
      <div class="vm-grid">${vms.length ? vms.map(vmCard).join('') : '<div class="empty"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><rect x="2" y="3" width="20" height="14" rx="2"/><path d="M8 21h8"/><path d="M12 17v4"/></svg><p>No virtual machines yet</p></div>'}</div>`;
  }).catch(() => { main.innerHTML = '<div style="text-align:center;padding:60px;color:var(--red)">Failed to load. Check your connection.</div>'; });
  return false;
}

function loadDetail(name) {
  const main = document.getElementById('main-content');
  main.innerHTML = '<div style="text-align:center;padding:80px 0"><div class="spinner"></div></div>';
  Promise.all([api('/vm/info/' + name), api('/vm/metrics/' + name).catch(() => ({}))]).then(([info, metrics]) => {
    const vm = info.vm || {};
    const m = metrics.metrics || {};
    const memStats = m.memory_stats || {};
    main.innerHTML = `
      <div class="detail-header">
        <a href="/" class="back" onclick="return loadVMs(event)">← Back to VMs</a>
        <h1>${vm.name}</h1>
        <p class="sub">${statusBadge(vm.state)}</p>
      </div>
      <div class="actions" style="margin-bottom:24px">
        ${vm.state === 'running' ? `<button class="btn btn-ghost" onclick="vmAction('${vm.name}','stop')">Stop</button><button class="btn btn-ghost" onclick="vmAction('${vm.name}','reboot')">Reboot</button>` : `<button class="btn btn-primary" onclick="vmAction('${vm.name}','start')">Start</button>`}
        <button class="btn btn-primary" onclick="window.location.href='/vm/vnc/console/${vm.name}'">Open Console</button>
      </div>
      <div class="detail-grid">
        <div class="detail-section">
          <h3>Configuration</h3>
          <div class="row"><span class="label">CPU</span><span class="value">${vm.cpu || '-'} vCPUs</span></div>
          <div class="row"><span class="label">Memory</span><span class="value">${vm.memory_mb || '-'} MB</span></div>
          <div class="row"><span class="label">IP Address</span><span class="value">${vm.ip_address || '-'}</span></div>
          <div class="row"><span class="label">State</span><span class="value">${vm.state}</span></div>
        </div>
        <div class="detail-section">
          <h3>Performance</h3>
          <div class="row"><span class="label">CPU Time</span><span class="value">${m.cpu_time_s || '-'} s</span></div>
          <div class="row"><span class="label">Memory (host)</span><span class="value">${m.memory_mb || '-'} MB</span></div>
          ${memStats.available ? `<div class="row"><span class="label">Mem Available</span><span class="value">${memStats.available} MB</span></div>` : ''}
          ${memStats.unused ? `<div class="row"><span class="label">Mem Unused</span><span class="value">${memStats.unused} MB</span></div>` : ''}
        </div>
      </div>`;
  }).catch(() => { main.innerHTML = '<div style="text-align:center;padding:60px;color:var(--red)">Failed to load VM details</div>'; });
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
  if (!confirm('Delete ' + name + '?')) return;
  fetch('/images/' + encodeURIComponent(name), {
    method: 'DELETE',
    headers: { 'Authorization': 'Bearer ' + TOKEN },
  }).then(r => { if (r.ok) { showToast(name + ' deleted'); loadISOs(); } else { showToast('Delete failed'); } }).catch(() => showToast('Error'));
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

function loadISOs() {
  const main = document.getElementById('main-content');
  main.innerHTML = '<div style="text-align:center;padding:80px 0"><div class="spinner"></div></div>';
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
}

function loadRepoImages() {
  const main = document.getElementById('main-content');
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
        <div class="vm-card" style="cursor:pointer" onclick="downloadRepoImage('${img.name}')">
          <div class="top"><div class="name">${img.name}</div></div>
          <div class="info"><div class="info-item" style="grid-column:span 2">${img.description}</div></div>
          <div class="actions" onclick="event.stopPropagation()">
            <button class="btn btn-primary" onclick="downloadRepoImage('${img.name}')">Download</button>
          </div>
        </div>`).join('');
      html += `</div>`;
    }
    if (!Object.keys(families).length) html += '<div class="empty"><p>No repository images available</p></div>';
    main.innerHTML = html;
  }).catch(() => { main.innerHTML = '<div style="text-align:center;padding:60px;color:var(--red)">Failed to load repos</div>'; });
}

function downloadRepoImage(name) {
  fetch('/images/download-cloud?name=' + encodeURIComponent(name), {
    method: 'POST',
    headers: { 'Authorization': 'Bearer ' + TOKEN },
  }).then(r => r.json().then(d => ({ ok: r.ok, data: d }))).then(({ ok, data }) => {
    if (!ok) { showToast(data.detail?.message || 'Download failed'); return; }
    showToast(name + ' downloaded');
  }).catch(() => showToast('Download error'));
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
      <input type="file" id="iso-file" style="width:100%;padding:10px 12px;margin-bottom:14px;background:#0a0a0f;border:1px solid #1e1e32;border-radius:6px;color:#fff;font-size:14px;font-family:inherit">
      <label style="display:block;margin-bottom:4px;font-size:13px;color:#71717a">Name <span style="color:#52525b">(optional, defaults to filename)</span></label>
      <input type="text" id="iso-upload-name" placeholder="my-image.iso" style="width:100%;padding:10px 12px;margin-bottom:14px;background:#0a0a0f;border:1px solid #1e1e32;border-radius:6px;color:#fff;font-size:14px;font-family:inherit">
      <div style="display:flex;gap:8px">
        <button type="submit" class="btn btn-primary" style="flex:1">Upload</button>
        <button type="button" class="btn btn-ghost" onclick="closeModal()" style="flex:1">Cancel</button>
      </div>
    </form>`;
  openModal();
}

function showDownloadIsoDialog() {
  document.getElementById('modal-title').textContent = 'Download ISO from URL';
  document.getElementById('modal-body').innerHTML = `
    <form onsubmit="downloadIso();return false">
      <label style="display:block;margin-bottom:4px;font-size:13px;color:#71717a">URL</label>
      <input type="url" id="iso-url" placeholder="https://releases.ubuntu.com/ubuntu.iso" required style="width:100%;padding:10px 12px;margin-bottom:14px;background:#0a0a0f;border:1px solid #1e1e32;border-radius:6px;color:#fff;font-size:14px;font-family:inherit">
      <label style="display:block;margin-bottom:4px;font-size:13px;color:#71717a">Name <span style="color:#52525b">(optional, defaults from URL)</span></label>
      <input type="text" id="iso-dl-name" placeholder="my-image.iso" style="width:100%;padding:10px 12px;margin-bottom:14px;background:#0a0a0f;border:1px solid #1e1e32;border-radius:6px;color:#fff;font-size:14px;font-family:inherit">
      <div style="display:flex;gap:8px">
        <button type="submit" class="btn btn-primary" style="flex:1">Download</button>
        <button type="button" class="btn btn-ghost" onclick="closeModal()" style="flex:1">Cancel</button>
      </div>
    </form>`;
  openModal();
}

function showCreateDialog() {
  api('/images/list').then(images => {
    const imgs = images.images || [];
    const opts = imgs.length ? imgs.map(i => `<option value="${i.path}">${i.name || i.path}</option>`).join('') : '<option value="">No images available</option>';
    document.getElementById('modal-title').textContent = 'Create VM';
    document.getElementById('modal-body').innerHTML = `
      <form id="create-vm-form" onsubmit="return createVM(event)">
        <label style="display:block;margin-bottom:4px;font-size:13px;color:#71717a">Name</label>
        <input type="text" id="vm-name" placeholder="my-vm" required style="width:100%;padding:10px 12px;margin-bottom:14px;background:#0a0a0f;border:1px solid #1e1e32;border-radius:6px;color:#fff;font-size:14px;font-family:inherit">

        <label style="display:block;margin-bottom:4px;font-size:13px;color:#71717a">Base Image</label>
        <select id="vm-image" required style="width:100%;padding:10px 12px;margin-bottom:14px;background:#0a0a0f;border:1px solid #1e1e32;border-radius:6px;color:#fff;font-size:14px;font-family:inherit">${opts}</select>

        <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:10px">
          <div><label style="display:block;margin-bottom:4px;font-size:13px;color:#71717a">CPU</label><input type="number" id="vm-cpu" value="1" min="1" style="width:100%;padding:10px 12px;margin-bottom:14px;background:#0a0a0f;border:1px solid #1e1e32;border-radius:6px;color:#fff;font-size:14px;font-family:inherit"></div>
          <div><label style="display:block;margin-bottom:4px;font-size:13px;color:#71717a">RAM (MB)</label><input type="number" id="vm-ram" value="512" min="128" step="128" style="width:100%;padding:10px 12px;margin-bottom:14px;background:#0a0a0f;border:1px solid #1e1e32;border-radius:6px;color:#fff;font-size:14px;font-family:inherit"></div>
          <div><label style="display:block;margin-bottom:4px;font-size:13px;color:#71717a">Disk (GB)</label><input type="number" id="vm-disk" value="10" min="1" style="width:100%;padding:10px 12px;margin-bottom:14px;background:#0a0a0f;border:1px solid #1e1e32;border-radius:6px;color:#fff;font-size:14px;font-family:inherit"></div>
        </div>

        <label style="display:block;margin-bottom:4px;font-size:13px;color:#71717a">ISO <span style="color:#52525b">(optional)</span></label>
        <input type="text" id="vm-iso" placeholder="/iso/ubuntu.iso" style="width:100%;padding:10px 12px;margin-bottom:14px;background:#0a0a0f;border:1px solid #1e1e32;border-radius:6px;color:#fff;font-size:14px;font-family:inherit">

        <label style="display:block;margin-bottom:4px;font-size:13px;color:#71717a">SSH Key <span style="color:#52525b">(optional)</span></label>
        <textarea id="vm-ssh" placeholder="ssh-rsa AAAAB3..." rows="2" style="width:100%;padding:10px 12px;margin-bottom:14px;background:#0a0a0f;border:1px solid #1e1e32;border-radius:6px;color:#fff;font-size:14px;font-family:inherit;resize:vertical"></textarea>

        <div style="display:flex;gap:8px;margin-top:4px">
          <button type="submit" class="btn btn-primary" style="flex:1">Create</button>
          <button type="button" class="btn btn-ghost" onclick="closeModal()" style="flex:1">Cancel</button>
        </div>
      </form>`;
    openModal();
  }).catch(() => showToast('Failed to load images'));
}

function createVM(e) {
  e.preventDefault();
  const body = {
    name: document.getElementById('vm-name').value,
    image: document.getElementById('vm-image').value,
    cpu: parseInt(document.getElementById('vm-cpu').value) || 1,
    memory_mb: parseInt(document.getElementById('vm-ram').value) || 512,
    disk_gb: parseInt(document.getElementById('vm-disk').value) || 10,
  };
  const iso = document.getElementById('vm-iso').value;
  if (iso) body.iso_path = iso;
  const ssh = document.getElementById('vm-ssh').value;
  if (ssh) body.cloud_init_ssh_key = ssh;
  closeModal();
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

function init() {
  api('/health/secured').then(d => {
    document.getElementById('user-info').textContent = d.user;
    document.getElementById('vm-submenu').classList.add('open');
    document.querySelector('.chevron').classList.add('rotated');
    loadVMs();
  }).catch(() => { window.location.href = '/auth/login-page?redirect=/'; });
}
init();
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
