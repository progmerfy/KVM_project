import asyncio
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse

from app.errors import ServiceError
from app.services.vm_manager import get_vnc_info

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/console/{name}")
async def vnc_console(name: str, host_uri: str = None):
    info = get_vnc_info(name, host_uri)
    if info is None:
        raise ServiceError(
            f"VM '{name}' not found", code="VM_NOT_FOUND", http_status=404
        )
    if info.get("state") != "running":
        raise ServiceError(
            f"VM '{name}' is not running", code="VM_NOT_RUNNING", http_status=400
        )

    html = _render_console_html(name)
    return HTMLResponse(content=html)


@router.websocket("/ws/{name}")
async def vnc_websocket(websocket: WebSocket, name: str, host_uri: str = None):
    await websocket.accept()

    info = get_vnc_info(name, host_uri)
    if info is None:
        await websocket.send_json({"error": "VM not found"})
        await websocket.close()
        return

    port = info.get("vnc_port")
    if not port:
        await websocket.send_json({"error": "VNC not available"})
        await websocket.close()
        return

    host = info.get("vnc_host", "127.0.0.1")
    logger.info("Proxying VNC for VM '%s' to %s:%s", name, host, port)

    try:
        reader, writer = await asyncio.open_connection(host, port)
    except Exception as e:
        logger.error("Failed to connect to VNC port %s: %s", port, e)
        await websocket.send_json({"error": f"Failed to connect to VNC: {e}"})
        await websocket.close()
        return

    async def ws_to_tcp():
        try:
            while True:
                data = await websocket.receive_bytes()
                writer.write(data)
                await writer.drain()
        except (WebSocketDisconnect, Exception):
            pass

    async def tcp_to_ws():
        try:
            while True:
                data = await reader.read(4096)
                if not data:
                    break
                await websocket.send_bytes(data)
        except Exception:
            pass
        finally:
            try:
                await websocket.close()
            except Exception:
                pass

    tasks = [asyncio.create_task(ws_to_tcp()), asyncio.create_task(tcp_to_ws())]
    try:
        await asyncio.gather(*tasks)
    except Exception:
        pass
    finally:
        writer.close()
        try:
            await writer.wait_closed()
        except Exception:
            pass
        for t in tasks:
            t.cancel()


def _render_console_html(name: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>VM Console - {name}</title>
<style>
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{ background: #000; display: flex; flex-direction: column; align-items: center; height: 100vh; }}
  #screen {{ width: 100%; height: 100%; }}
  .toolbar {{
    background: #1a1a2e; color: #fff; width: 100%;
    padding: 8px 16px; display: flex; align-items: center;
    font-family: monospace; font-size: 14px;
  }}
  .toolbar .title {{ flex: 1; }}
  .toolbar .status {{
    padding: 4px 12px; border-radius: 4px; font-size: 12px;
    background: #e74c3c; color: #fff;
  }}
  .toolbar .status.connected {{ background: #2ecc71; }}
  #toast {{
    position: fixed; bottom: 20px; left: 50%; transform: translateX(-50%);
    background: #2ecc71; color: #000; padding: 6px 16px;
    border-radius: 4px; font-family: monospace; font-size: 13px;
    z-index: 1000; transition: opacity 0.3s; opacity: 0;
  }}
  #toast.show {{ opacity: 1; }}
  .hint {{
    position: fixed; bottom: 20px; right: 20px;
    color: #555; font-family: monospace; font-size: 11px;
    z-index: 999;
  }}
</style>
</head>
<body>
<div class="toolbar">
  <span class="title">VM Console: {name}</span>
  <span class="status" id="status">Disconnected</span>
</div>
<div id="screen"></div>
<div id="toast"></div>
<div class="hint">Ctrl+Shift+V to paste</div>

<script type="module">
import RFB from '/static/novnc/rfb.js';

const WS_URL = `${{location.protocol === 'https:' ? 'wss:' : 'ws:'}}//${{location.host}}/vm/vnc/ws/{name}`;
const statusEl = document.getElementById('status');
const toastEl = document.getElementById('toast');
let toastTimer;

function showToast(msg) {{
  toastEl.textContent = msg;
  toastEl.classList.add('show');
  if (toastTimer) clearTimeout(toastTimer);
  toastTimer = setTimeout(() => toastEl.classList.remove('show'), 2000);
}}

function setConnected(yes) {{
  statusEl.textContent = yes ? 'Connected' : 'Disconnected';
  statusEl.className = 'status' + (yes ? ' connected' : '');
}}

const rfb = new RFB(document.getElementById('screen'), WS_URL, {{
  credentials: {{ password: '' }},
  shared: true,
  wsProtocols: []
}});
rfb.addEventListener('connect', () => setConnected(true));
rfb.addEventListener('disconnect', () => setConnected(false));
rfb.addEventListener('securityfailure', (e) => {{
  console.error('Security failure:', e.detail);
}});

// Receive clipboard from VM → copy to system clipboard
rfb.addEventListener('clipboard', (e) => {{
  const text = e.detail.text;
  if (text) {{
    navigator.clipboard.writeText(text).catch(() => {{}});
    showToast('Copied from VM');
  }}
}});

// Map char → physical key code (for noVNC keyboard state)
function keyCode(c) {{
  const code = c.charCodeAt(0);
  if (code >= 65 && code <= 90) return 'Key' + c;
  if (code >= 97 && code <= 122) return 'Key' + c.toUpperCase();
  if (code >= 48 && code <= 57) return 'Digit' + c;
  const map = {{
    32: 'Space', 13: 'Enter', 9: 'Tab', 8: 'Backspace',
    192: 'Backquote', 189: 'Minus', 187: 'Equal',
    219: 'BracketLeft', 221: 'BracketRight', 220: 'Backslash',
    186: 'Semicolon', 222: 'Quote', 188: 'Comma', 190: 'Period', 191: 'Slash',
  }};
  return map[code] || null;
}}

// Type text as keystrokes into VM via noVNC keyboard
function typeText(text) {{
  let i = 0;
  function next() {{
    if (i >= text.length) {{ showToast('Pasted ' + text.length + ' chars'); return; }}
    const ch = text[i++];
    const code = ch.charCodeAt(0);
    const kc = keyCode(ch);

    if (code === 10) {{
      rfb._keyboard.sendKey(0xFF0D, 'Enter', true);
      setTimeout(() => {{ rfb._keyboard.sendKey(0xFF0D, 'Enter', false); setTimeout(next, 10); }}, 10);
    }} else if (code >= 65 && code <= 90) {{ // uppercase
      rfb._keyboard.sendKey(0xFFE1, 'ShiftLeft', true);
      rfb._keyboard.sendKey(code + 32, kc, true);
      setTimeout(() => {{
        rfb._keyboard.sendKey(code + 32, kc, false);
        rfb._keyboard.sendKey(0xFFE1, 'ShiftLeft', false);
        setTimeout(next, 10);
      }}, 10);
    }} else {{
      rfb._keyboard.sendKey(code, kc, true);
      setTimeout(() => {{ rfb._keyboard.sendKey(code, kc, false); setTimeout(next, 10); }}, 10);
    }}
  }}
  next();
}}

// Ctrl+Shift+V → read clipboard → type into VM
window.addEventListener('keydown', (e) => {{
  if (e.ctrlKey && e.shiftKey && (e.key === 'V' || e.key === 'v')) {{
    e.preventDefault();
    e.stopPropagation();
    navigator.clipboard.readText().then(text => {{
      if (text) typeText(text);
    }}).catch(() => showToast('Cannot read clipboard'));
  }}
}}, true);

rfb.scaleViewport = true;
rfb.resizeSession = false;
</script>
</body>
</html>"""
