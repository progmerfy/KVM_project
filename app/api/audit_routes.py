from fastapi import APIRouter, Depends, Query

from app.auth import get_current_user
from app.database import create_audit_log, list_audit_logs
from app.errors import ServiceError

router = APIRouter()


@router.get("/logs")
def api_audit_logs(
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    user_id: int = Query(None),
    action: str = Query(None),
    resource_type: str = Query(None),
    current_user: dict = Depends(get_current_user),
):
    if not current_user.get("is_admin"):
        raise ServiceError("Access denied", code="FORBIDDEN", http_status=403)
    logs = list_audit_logs(
        limit=limit, offset=offset,
        user_id=user_id, action=action,
        resource_type=resource_type,
    )
    return {"status": "ok", "logs": logs}
