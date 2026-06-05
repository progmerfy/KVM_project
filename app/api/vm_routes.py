from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.api.schemas import (
    VMCreateRequest,
    VMActionRequest,
    VMISORequest,
    VMResizeRequest,
    VMAttachDiskRequest,
    VMDetachDiskRequest,
    VMNetworkRequest,
    VMImportRequest,
    VMCloneRequest,
    VMBackupRequest,
    VMRestoreRequest,
)
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
    resize_vm,
    attach_disk,
    detach_disk_vm,
    snapshot_create,
    snapshot_list,
    snapshot_revert,
    snapshot_delete,
    network_create,
    network_list,
    network_delete,
    export_vm,
    import_vm,
    clone_vm,
    backup_vm,
    restore_vm,
    get_metrics,
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


@router.post("/snapshot/create")
def api_snapshot_create(name: str, snap_name: str, host_uri: str = None):
    result = snapshot_create(name, snap_name, host_uri)
    return {"status": "ok", "snapshot": result}


@router.get("/snapshot/list/{name}")
def api_snapshot_list(name: str, host_uri: str = None):
    snaps = snapshot_list(name, host_uri)
    return {"status": "ok", "snapshots": snaps}


@router.post("/snapshot/revert")
def api_snapshot_revert(name: str, snap_name: str, host_uri: str = None):
    result = snapshot_revert(name, snap_name, host_uri)
    return {"status": "ok", "snapshot": result}


@router.delete("/snapshot/delete")
def api_snapshot_delete(name: str, snap_name: str, host_uri: str = None):
    result = snapshot_delete(name, snap_name, host_uri)
    return {"status": "ok", "message": f"Snapshot '{snap_name}' deleted"}


@router.post("/resize")
def api_resize_vm(req: VMResizeRequest):
    result = resize_vm(req)
    return {"status": "ok", "vm": result}


@router.post("/attach-disk")
def api_attach_disk(req: VMAttachDiskRequest):
    result = attach_disk(req.name, req.size_gb, req.target_dev, req.host_uri)
    return {"status": "ok", "disk": result}


@router.post("/detach-disk")
def api_detach_disk(req: VMDetachDiskRequest):
    result = detach_disk_vm(req.name, req.target_dev, req.host_uri)
    return {"status": "ok", "disk": result}


@router.get("/export/{name}")
def api_export_vm(name: str, host_uri: str = None):
    result = export_vm(name, host_uri)
    return {"status": "ok", "export": result}


@router.post("/import")
def api_import_vm(req: VMImportRequest):
    result = import_vm(req.xml, req.disk_paths, req.host_uri)
    return {"status": "ok", "vm": result}


@router.post("/clone")
def api_clone_vm(req: VMCloneRequest):
    result = clone_vm(req.name, req.new_name, req.host_uri)
    return {"status": "ok", "vm": result}


@router.post("/backup")
def api_backup_vm(req: VMBackupRequest):
    result = backup_vm(req.name, req.host_uri)
    return {"status": "ok", "backup": result}


@router.post("/restore")
def api_restore_vm(req: VMRestoreRequest):
    result = restore_vm(req.backup_dir, req.new_name, req.host_uri)
    return {"status": "ok", "vm": result}


@router.get("/metrics/{name}")
def api_metrics(name: str, host_uri: str = None):
    result = get_metrics(name, host_uri)
    return {"status": "ok", "metrics": result}


@router.post("/network/create")
def api_network_create(req: VMNetworkRequest):
    result = network_create(req.name, req.bridge, req.subnet, req.host_uri)
    return {"status": "ok", "network": result}


@router.get("/network/list")
def api_network_list(host_uri: str = None):
    nets = network_list(host_uri)
    return {"status": "ok", "networks": nets}


@router.delete("/network/delete")
def api_network_delete(name: str, host_uri: str = None):
    result = network_delete(name, host_uri)
    return {"status": "ok", "message": f"Network '{name}' deleted"}


@router.get("/vnc/info/{name}")
def api_vnc_info(name: str, host_uri: str = None):
    info = get_vnc_info(name, host_uri)
    if info is None:
        raise ServiceError(
            f"VM '{name}' not found", code="VM_NOT_FOUND", http_status=404
        )
    return {"status": "ok", "vnc": info}
