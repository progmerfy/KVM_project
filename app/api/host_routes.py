from fastapi import APIRouter

from app.services import host_manager

router = APIRouter()


@router.get("/info")
def api_host_info():
    return {"status": "ok", "host": host_manager.get_host_info()}


@router.get("/stats")
def api_host_stats():
    return {"status": "ok", "stats": host_manager.get_host_stats()}
