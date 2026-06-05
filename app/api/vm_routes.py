from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.api.schemas import VMCreateRequest, VMActionRequest, VMISORequest
from app.services.vm_manager import (
    create_vm,
    start_vm,
    stop_vm,
    reboot_vm,
    reset_vm,
    delete_vm,
    get_vm_status,
    list_vms,
    get_vm_info,
    attach_iso,
    detach_iso,
    get_vnc_info,
)
from app.errors import ServiceError
from app.api.vnc import router as vnc_router

router = APIRouter()
router.include_router(vnc_router, prefix="/vnc")


@router.post("/create", status_code=202)
def api_create_vm(req: VMCreateRequest):
    result = create_vm(req)
    return JSONResponse(
        status_code=202,
        content={"task_id": result["name"], "status": "accepted", "vm": result},
    )


@router.post("/start")
def api_start_vm(req: VMActionRequest):
    start_vm(req)
    return {"status": "ok"}


@router.post("/stop")
def api_stop_vm(req: VMActionRequest):
    stop_vm(req)
    return {"status": "ok"}


@router.post("/reboot")
def api_reboot_vm(req: VMActionRequest):
    reboot_vm(req)
    return {"status": "ok"}


@router.post("/reset")
def api_reset_vm(req: VMActionRequest):
    reset_vm(req)
    return {"status": "ok"}


@router.delete("/delete")
def api_delete_vm(req: VMActionRequest):
    delete_vm(req)
    return {"status": "ok"}


@router.get("/status/{name}")
def api_vm_status(name: str, host_uri: str = None):
    status = get_vm_status(name, host_uri)
    if status == "not-found":
        raise ServiceError(
            f"VM '{name}' not found", code="VM_NOT_FOUND", http_status=404
        )
    return {"status": "ok", "vm": {"name": name, "state": status}}


@router.get("/list")
def api_list_vms(host_uri: str = None):
    vms = list_vms(host_uri)
    return {"status": "ok", "vms": vms}


@router.get("/info/{name}")
def api_vm_info(name: str, host_uri: str = None):
    info = get_vm_info(name, host_uri)
    if info is None:
        raise ServiceError(
            f"VM '{name}' not found", code="VM_NOT_FOUND", http_status=404
        )
    return {"status": "ok", "vm": info}


@router.post("/attach-iso")
def api_attach_iso(req: VMISORequest):
    attach_iso(req)
    return {"status": "ok", "message": f"ISO '{req.iso_path}' attached to '{req.name}'"}


@router.post("/detach-iso")
def api_detach_iso(req: VMActionRequest):
    detach_iso(req.name, req.host_uri)
    return {"status": "ok", "message": f"CDROM detached from '{req.name}'"}


@router.get("/vnc/info/{name}")
def api_vnc_info(name: str, host_uri: str = None):
    info = get_vnc_info(name, host_uri)
    if info is None:
        raise ServiceError(
            f"VM '{name}' not found", code="VM_NOT_FOUND", http_status=404
        )
    return {"status": "ok", "vnc": info}
