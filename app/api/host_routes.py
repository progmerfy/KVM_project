from fastapi import APIRouter, Depends

from app.services import host_manager
from app.services.vm_manager import network_list, get_network_leases
from app.auth import get_current_user

router = APIRouter()


@router.get("/info")
def api_host_info():
    return {"status": "ok", "host": host_manager.get_host_info()}


@router.get("/stats")
def api_host_stats():
    return {"status": "ok", "stats": host_manager.get_host_stats()}


@router.get("/networks")
def api_host_networks(current_user: dict = Depends(get_current_user)):
    nets = network_list()
    leases = get_network_leases()
    return {
        "status": "ok",
        "networks": nets,
        "leases": leases,
    }
