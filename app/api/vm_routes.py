from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

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
from typing import Optional

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
    list_backups_for_vm,
    delete_backup,
    get_metrics,
    authorize_vm_access,
    set_vm_autostart,
)
from app.errors import ServiceError
from app.api.vnc import router as vnc_router
from app.auth import get_current_user
from app.database import (
    create_backup_schedule,
    list_backup_schedules,
    get_backup_schedule,
    update_backup_schedule,
    delete_backup_schedule,
    create_audit_log,
)

logger = __import__("logging").getLogger(__name__)


def _audit_log(*args, **kwargs):
    try:
        create_audit_log(*args, **kwargs)
    except Exception as e:
        logger.warning("audit log failed: %s", e)


router = APIRouter()
router.include_router(vnc_router, prefix="/vnc")


@router.post("/create", status_code=202)
def api_create_vm(req: VMCreateRequest, request: Request, current_user: dict = Depends(get_current_user)):
    result = create_vm(req, owner_id=current_user["id"])
    _audit_log(current_user["id"], current_user["username"], "create", "vm", req.name, ip_address=request.client.host if request.client else None)
    return JSONResponse(
        status_code=202,
        content={"task_id": result["name"], "status": "accepted", "vm": result},
    )


@router.post("/start")
def api_start_vm(req: VMActionRequest, request: Request, current_user: dict = Depends(get_current_user)):
    if not authorize_vm_access(req.name, current_user):
        _audit_log(current_user["id"], current_user["username"], "start", "vm", req.name, success=False, ip_address=request.client.host if request.client else None)
        raise ServiceError("Access denied", code="FORBIDDEN", http_status=403)
    start_vm(req)
    _audit_log(current_user["id"], current_user["username"], "start", "vm", req.name, ip_address=request.client.host if request.client else None)
    return {"status": "ok"}


@router.post("/stop")
def api_stop_vm(req: VMActionRequest, request: Request, current_user: dict = Depends(get_current_user)):
    if not authorize_vm_access(req.name, current_user):
        _audit_log(current_user["id"], current_user["username"], "stop", "vm", req.name, success=False, ip_address=request.client.host if request.client else None)
        raise ServiceError("Access denied", code="FORBIDDEN", http_status=403)
    stop_vm(req)
    _audit_log(current_user["id"], current_user["username"], "stop", "vm", req.name, ip_address=request.client.host if request.client else None)
    return {"status": "ok"}


@router.post("/reboot")
def api_reboot_vm(req: VMActionRequest, current_user: dict = Depends(get_current_user)):
    if not authorize_vm_access(req.name, current_user):
        raise ServiceError("Access denied", code="FORBIDDEN", http_status=403)
    reboot_vm(req)
    return {"status": "ok"}


@router.post("/reset")
def api_reset_vm(req: VMActionRequest, current_user: dict = Depends(get_current_user)):
    if not authorize_vm_access(req.name, current_user):
        raise ServiceError("Access denied", code="FORBIDDEN", http_status=403)
    reset_vm(req)
    return {"status": "ok"}


@router.post("/autostart")
def api_vm_autostart(name: str, enable: bool, current_user: dict = Depends(get_current_user), host_uri: str = None):
    if not authorize_vm_access(name, current_user):
        raise ServiceError("Access denied", code="FORBIDDEN", http_status=403)
    result = set_vm_autostart(name, enable, host_uri)
    return {"status": "ok", "autostart": result}


@router.post("/delete")
@router.delete("/delete")
def api_delete_vm(req: VMActionRequest, request: Request, current_user: dict = Depends(get_current_user)):
    if not authorize_vm_access(req.name, current_user):
        _audit_log(current_user["id"], current_user["username"], "delete", "vm", req.name, success=False, ip_address=request.client.host if request.client else None)
        raise ServiceError("Access denied", code="FORBIDDEN", http_status=403)
    delete_vm(req)
    _audit_log(current_user["id"], current_user["username"], "delete", "vm", req.name, ip_address=request.client.host if request.client else None)
    return {"status": "ok"}


@router.get("/status/{name}")
def api_vm_status(name: str, current_user: dict = Depends(get_current_user), host_uri: str = None):
    if not authorize_vm_access(name, current_user):
        raise ServiceError("Access denied", code="FORBIDDEN", http_status=403)
    status = get_vm_status(name, host_uri)
    if status == "not-found":
        raise ServiceError(
            f"VM '{name}' not found", code="VM_NOT_FOUND", http_status=404
        )
    return {"status": "ok", "vm": {"name": name, "state": status}}


@router.get("/list")
def api_list_vms(current_user: dict = Depends(get_current_user), host_uri: str = None):
    owner_id = None if current_user.get("is_admin") else current_user["id"]
    vms = list_vms(host_uri, owner_id=owner_id)
    return {"status": "ok", "vms": vms}


@router.get("/info/{name}")
def api_vm_info(name: str, current_user: dict = Depends(get_current_user), host_uri: str = None):
    if not authorize_vm_access(name, current_user):
        raise ServiceError("Access denied", code="FORBIDDEN", http_status=403)
    info = get_vm_info(name, host_uri)
    if info is None:
        raise ServiceError(
            f"VM '{name}' not found", code="VM_NOT_FOUND", http_status=404
        )
    return {"status": "ok", "vm": info}


@router.post("/attach-iso")
def api_attach_iso(req: VMISORequest, current_user: dict = Depends(get_current_user)):
    if not authorize_vm_access(req.name, current_user):
        raise ServiceError("Access denied", code="FORBIDDEN", http_status=403)
    attach_iso(req)
    return {"status": "ok", "message": f"ISO '{req.iso_path}' attached to '{req.name}'"}


@router.post("/detach-iso")
def api_detach_iso(req: VMActionRequest, current_user: dict = Depends(get_current_user)):
    if not authorize_vm_access(req.name, current_user):
        raise ServiceError("Access denied", code="FORBIDDEN", http_status=403)
    detach_iso(req.name, req.host_uri)
    return {"status": "ok", "message": f"CDROM detached from '{req.name}'"}


@router.post("/snapshot/create")
def api_snapshot_create(name: str, snap_name: str, request: Request, current_user: dict = Depends(get_current_user), host_uri: str = None):
    if not authorize_vm_access(name, current_user):
        _audit_log(current_user["id"], current_user["username"], "snapshot_create", "vm", name, success=False, ip_address=request.client.host if request.client else None)
        raise ServiceError("Access denied", code="FORBIDDEN", http_status=403)
    result = snapshot_create(name, snap_name, host_uri)
    _audit_log(current_user["id"], current_user["username"], "snapshot_create", "vm", name, details=f"snapshot={snap_name}", ip_address=request.client.host if request.client else None)
    return {"status": "ok", "snapshot": result}


@router.get("/snapshot/list/{name}")
def api_snapshot_list(name: str, current_user: dict = Depends(get_current_user), host_uri: str = None):
    if not authorize_vm_access(name, current_user):
        raise ServiceError("Access denied", code="FORBIDDEN", http_status=403)
    snaps = snapshot_list(name, host_uri)
    return {"status": "ok", "snapshots": snaps}


@router.post("/snapshot/revert")
def api_snapshot_revert(name: str, snap_name: str, current_user: dict = Depends(get_current_user), host_uri: str = None):
    if not authorize_vm_access(name, current_user):
        raise ServiceError("Access denied", code="FORBIDDEN", http_status=403)
    result = snapshot_revert(name, snap_name, host_uri)
    return {"status": "ok", "snapshot": result}


@router.delete("/snapshot/delete")
def api_snapshot_delete(name: str, snap_name: str, request: Request, current_user: dict = Depends(get_current_user), host_uri: str = None):
    if not authorize_vm_access(name, current_user):
        _audit_log(current_user["id"], current_user["username"], "snapshot_delete", "vm", name, success=False, ip_address=request.client.host if request.client else None)
        raise ServiceError("Access denied", code="FORBIDDEN", http_status=403)
    result = snapshot_delete(name, snap_name, host_uri)
    _audit_log(current_user["id"], current_user["username"], "snapshot_delete", "vm", name, details=f"snapshot={snap_name}", ip_address=request.client.host if request.client else None)
    return {"status": "ok", "message": f"Snapshot '{snap_name}' deleted"}


@router.post("/resize")
def api_resize_vm(req: VMResizeRequest, current_user: dict = Depends(get_current_user)):
    if not authorize_vm_access(req.name, current_user):
        raise ServiceError("Access denied", code="FORBIDDEN", http_status=403)
    result = resize_vm(req)
    return {"status": "ok", "vm": result}


@router.post("/attach-disk")
def api_attach_disk(req: VMAttachDiskRequest, current_user: dict = Depends(get_current_user)):
    if not authorize_vm_access(req.name, current_user):
        raise ServiceError("Access denied", code="FORBIDDEN", http_status=403)
    result = attach_disk(req.name, req.size_gb, req.target_dev, req.host_uri)
    return {"status": "ok", "disk": result}


@router.post("/detach-disk")
def api_detach_disk(req: VMDetachDiskRequest, current_user: dict = Depends(get_current_user)):
    if not authorize_vm_access(req.name, current_user):
        raise ServiceError("Access denied", code="FORBIDDEN", http_status=403)
    result = detach_disk_vm(req.name, req.target_dev, req.host_uri)
    return {"status": "ok", "disk": result}


@router.get("/export/{name}")
def api_export_vm(name: str, current_user: dict = Depends(get_current_user), host_uri: str = None):
    if not authorize_vm_access(name, current_user):
        raise ServiceError("Access denied", code="FORBIDDEN", http_status=403)
    result = export_vm(name, host_uri)
    return {"status": "ok", "export": result}


@router.post("/import")
def api_import_vm(req: VMImportRequest, current_user: dict = Depends(get_current_user)):
    if not current_user.get("is_admin"):
        raise ServiceError("Access denied", code="FORBIDDEN", http_status=403)
    result = import_vm(req.xml, req.disk_paths, req.host_uri)
    return {"status": "ok", "vm": result}


@router.post("/clone")
def api_clone_vm(req: VMCloneRequest, request: Request, current_user: dict = Depends(get_current_user)):
    if not authorize_vm_access(req.name, current_user):
        _audit_log(current_user["id"], current_user["username"], "clone", "vm", req.name, success=False, ip_address=request.client.host if request.client else None)
        raise ServiceError("Access denied", code="FORBIDDEN", http_status=403)
    result = clone_vm(req.name, req.new_name, req.host_uri, owner_id=current_user["id"])
    _audit_log(current_user["id"], current_user["username"], "clone", "vm", req.new_name, details=f"source={req.name}", ip_address=request.client.host if request.client else None)
    return {"status": "ok", "vm": result}


@router.post("/backup")
def api_backup_vm(req: VMBackupRequest, request: Request, current_user: dict = Depends(get_current_user)):
    if not authorize_vm_access(req.name, current_user):
        _audit_log(current_user["id"], current_user["username"], "backup", "vm", req.name, success=False, ip_address=request.client.host if request.client else None)
        raise ServiceError("Access denied", code="FORBIDDEN", http_status=403)
    result = backup_vm(req.name, req.host_uri)
    _audit_log(current_user["id"], current_user["username"], "backup", "vm", req.name, details=f"backup_dir={result.get('backup_dir')}", ip_address=request.client.host if request.client else None)
    return {"status": "ok", "backup": result}


@router.get("/backup/list/{name}")
def api_list_backups(name: str, current_user: dict = Depends(get_current_user)):
    if not authorize_vm_access(name, current_user):
        raise ServiceError("Access denied", code="FORBIDDEN", http_status=403)
    backups = list_backups_for_vm(name)
    return {"status": "ok", "backups": backups}


@router.delete("/backup/delete")
def api_delete_backup(backup_dir: str, request: Request, current_user: dict = Depends(get_current_user)):
    if not current_user.get("is_admin"):
        _audit_log(current_user["id"], current_user["username"], "backup_delete", "vm", "unknown", success=False, ip_address=request.client.host if request.client else None)
        raise ServiceError("Access denied", code="FORBIDDEN", http_status=403)
    delete_backup(backup_dir)
    _audit_log(current_user["id"], current_user["username"], "backup_delete", "vm", backup_dir, ip_address=request.client.host if request.client else None)
    return {"status": "ok", "message": "Backup deleted"}


@router.post("/restore")
def api_restore_vm(req: VMRestoreRequest, current_user: dict = Depends(get_current_user)):
    if not current_user.get("is_admin"):
        raise ServiceError("Access denied", code="FORBIDDEN", http_status=403)
    result = restore_vm(req.backup_dir, req.new_name, req.host_uri)
    return {"status": "ok", "vm": result}


@router.get("/metrics/{name}")
def api_metrics(name: str, current_user: dict = Depends(get_current_user), host_uri: str = None):
    if not authorize_vm_access(name, current_user):
        raise ServiceError("Access denied", code="FORBIDDEN", http_status=403)
    result = get_metrics(name, host_uri)
    return {"status": "ok", "metrics": result}


@router.post("/network/create")
def api_network_create(req: VMNetworkRequest, current_user: dict = Depends(get_current_user)):
    if not current_user.get("is_admin"):
        raise ServiceError("Access denied", code="FORBIDDEN", http_status=403)
    result = network_create(req.name, req.bridge, req.subnet, req.host_uri)
    return {"status": "ok", "network": result}


@router.get("/network/list")
def api_network_list(current_user: dict = Depends(get_current_user), host_uri: str = None):
    if not current_user.get("is_admin"):
        raise ServiceError("Access denied", code="FORBIDDEN", http_status=403)
    nets = network_list(host_uri)
    return {"status": "ok", "networks": nets}


@router.delete("/network/delete")
def api_network_delete(name: str, current_user: dict = Depends(get_current_user), host_uri: str = None):
    if not current_user.get("is_admin"):
        raise ServiceError("Access denied", code="FORBIDDEN", http_status=403)
    result = network_delete(name, host_uri)
    return {"status": "ok", "message": f"Network '{name}' deleted"}


# ── Backup schedule (admin only) ──────────────────────────────────

class BackupScheduleCreate(BaseModel):
    vm_name: str
    cron_expression: str
    retention: int = 7

class BackupScheduleUpdate(BaseModel):
    cron_expression: Optional[str] = None
    retention: Optional[int] = None
    enabled: Optional[bool] = None


@router.get("/backup/schedules")
def api_list_backup_schedules(current_user: dict = Depends(get_current_user)):
    if not current_user.get("is_admin"):
        raise ServiceError("Access denied", code="FORBIDDEN", http_status=403)
    return {"status": "ok", "schedules": list_backup_schedules()}


@router.post("/backup/schedules")
def api_create_backup_schedule(req: BackupScheduleCreate, request: Request, current_user: dict = Depends(get_current_user)):
    if not current_user.get("is_admin"):
        _audit_log(current_user["id"], current_user["username"], "schedule_create", "backup", req.vm_name, success=False, ip_address=request.client.host if request.client else None)
        raise ServiceError("Access denied", code="FORBIDDEN", http_status=403)
    try:
        from croniter import croniter
        if not croniter.is_valid(req.cron_expression):
            raise ServiceError("Invalid cron expression", code="INVALID_CRON", http_status=400)
    except ImportError:
        pass
    try:
        sched = create_backup_schedule(req.vm_name, req.cron_expression, req.retention)
        _audit_log(current_user["id"], current_user["username"], "schedule_create", "backup", req.vm_name, details=f"cron={req.cron_expression},retention={req.retention}", ip_address=request.client.host if request.client else None)
        return {"status": "ok", "schedule": sched}
    except ValueError as e:
        raise ServiceError(str(e), code="SCHEDULE_EXISTS", http_status=409)


@router.put("/backup/schedules/{schedule_id}")
def api_update_backup_schedule(schedule_id: int, req: BackupScheduleUpdate, request: Request, current_user: dict = Depends(get_current_user)):
    if not current_user.get("is_admin"):
        _audit_log(current_user["id"], current_user["username"], "schedule_update", "backup", str(schedule_id), success=False, ip_address=request.client.host if request.client else None)
        raise ServiceError("Access denied", code="FORBIDDEN", http_status=403)
    sched = update_backup_schedule(schedule_id, req.cron_expression, req.retention, req.enabled)
    if not sched:
        raise ServiceError("Schedule not found", code="NOT_FOUND", http_status=404)
    _audit_log(current_user["id"], current_user["username"], "schedule_update", "backup", sched["vm_name"], details=f"schedule_id={schedule_id}", ip_address=request.client.host if request.client else None)
    return {"status": "ok", "schedule": sched}


@router.delete("/backup/schedules/{schedule_id}")
def api_delete_backup_schedule(schedule_id: int, request: Request, current_user: dict = Depends(get_current_user)):
    if not current_user.get("is_admin"):
        _audit_log(current_user["id"], current_user["username"], "schedule_delete", "backup", str(schedule_id), success=False, ip_address=request.client.host if request.client else None)
        raise ServiceError("Access denied", code="FORBIDDEN", http_status=403)
    sched = get_backup_schedule(schedule_id)
    if not sched:
        raise ServiceError("Schedule not found", code="NOT_FOUND", http_status=404)
    delete_backup_schedule(schedule_id)
    _audit_log(current_user["id"], current_user["username"], "schedule_delete", "backup", sched["vm_name"], details=f"schedule_id={schedule_id}", ip_address=request.client.host if request.client else None)
    return {"status": "ok", "message": "Schedule deleted"}


@router.get("/vnc/info/{name}")
def api_vnc_info(name: str, current_user: dict = Depends(get_current_user), host_uri: str = None):
    if not authorize_vm_access(name, current_user):
        raise ServiceError("Access denied", code="FORBIDDEN", http_status=403)
    info = get_vnc_info(name, host_uri)
    if info is None:
        raise ServiceError(
            f"VM '{name}' not found", code="VM_NOT_FOUND", http_status=404
        )
    return {"status": "ok", "vnc": info}
