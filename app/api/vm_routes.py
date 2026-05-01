from fastapi import APIRouter, HTTPException
from app.api.schemas import VMCreateRequest, VMActionRequest
from app.services.vm_manager import (
    create_vm,
    start_vm,
    stop_vm,
    delete_vm,
    get_vm_status,
)
from app.services.vm_manager import list_vms, get_vm_info
from app.errors import ServiceError, InfrastructureError

router = APIRouter()


@router.post("/create")
def api_create_vm(req: VMCreateRequest):
    try:
        result = create_vm(req)
        return {"status": "ok", "vm": result}
    except ServiceError as e:
        raise HTTPException(
            status_code=e.http_status, detail={"code": e.code, "message": e.message}
        )
    except InfrastructureError as e:
        raise HTTPException(
            status_code=e.http_status, detail={"code": e.code, "message": e.message}
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/start")
def api_start_vm(req: VMActionRequest):
    try:
        start_vm(req)
        return {"status": "ok"}
    except ServiceError as e:
        raise HTTPException(
            status_code=e.http_status, detail={"code": e.code, "message": e.message}
        )
    except InfrastructureError as e:
        raise HTTPException(
            status_code=e.http_status, detail={"code": e.code, "message": e.message}
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/stop")
def api_stop_vm(req: VMActionRequest):
    try:
        stop_vm(req)
        return {"status": "ok"}
    except ServiceError as e:
        raise HTTPException(
            status_code=e.http_status, detail={"code": e.code, "message": e.message}
        )
    except InfrastructureError as e:
        raise HTTPException(
            status_code=e.http_status, detail={"code": e.code, "message": e.message}
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/delete")
def api_delete_vm(req: VMActionRequest):
    try:
        delete_vm(req)
        return {"status": "ok"}
    except ServiceError as e:
        raise HTTPException(
            status_code=e.http_status, detail={"code": e.code, "message": e.message}
        )
    except InfrastructureError as e:
        raise HTTPException(
            status_code=e.http_status, detail={"code": e.code, "message": e.message}
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/status/{name}")
def api_vm_status(name: str, host_uri: str = None):
    try:
        status = get_vm_status(name, host_uri)
        if status == "not-found":
            raise ServiceError(
                f"VM '{name}' not found", code="VM_NOT_FOUND", http_status=404
            )
        return {"status": "ok", "vm": {"name": name, "state": status}}
    except ServiceError as e:
        raise HTTPException(
            status_code=e.http_status, detail={"code": e.code, "message": e.message}
        )
    except InfrastructureError as e:
        raise HTTPException(
            status_code=e.http_status, detail={"code": e.code, "message": e.message}
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/list")
def api_list_vms(host_uri: str = None):
    try:
        vms = []
        vms = list_vms(host_uri)
        return {"status": "ok", "vms": vms}
    except ServiceError as e:
        raise HTTPException(
            status_code=e.http_status, detail={"code": e.code, "message": e.message}
        )
    except InfrastructureError as e:
        raise HTTPException(
            status_code=e.http_status, detail={"code": e.code, "message": e.message}
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/info/{name}")
def api_vm_info(name: str, host_uri: str = None):
    try:
        info = get_vm_info(name, host_uri)
        if info is None:
            raise ServiceError(
                f"VM '{name}' not found", code="VM_NOT_FOUND", http_status=404
            )
        return {"status": "ok", "vm": info}
    except ServiceError as e:
        raise HTTPException(
            status_code=e.http_status, detail={"code": e.code, "message": e.message}
        )
    except InfrastructureError as e:
        raise HTTPException(
            status_code=e.http_status, detail={"code": e.code, "message": e.message}
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
