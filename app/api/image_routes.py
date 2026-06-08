import os
import logging
import subprocess
from urllib.parse import urlparse

from fastapi import APIRouter, UploadFile, File, Form
from fastapi.responses import JSONResponse

from app.services import image_manager
from app.config import settings
from app.errors import ServiceError

logger = logging.getLogger(__name__)
router = APIRouter()


def _get_image_dir() -> str:
    return settings.storage_pool or "/var/lib/libvirt/images"


@router.get("/list")
def api_list_images():
    images = image_manager.list_images()
    return {"status": "ok", "images": [img.model_dump() for img in images]}


@router.get("/cloud/list")
def api_list_cloud_images():
    return {"status": "ok", "cloud_images": image_manager.list_cloud_images()}


@router.get("/repo/list")
def api_list_repo_images():
    return {"status": "ok", "families": image_manager.list_repo_images()}


@router.post("/download-cloud")
def api_download_cloud_image(name: str):
    img = image_manager.download_cloud_image(name)
    return {"status": "ok", "image": img.model_dump()}


@router.post("/download-repo-iso")
def api_download_repo_iso(name: str):
    img = image_manager.download_repo_iso(name)
    return {"status": "ok", "image": img.model_dump()}


@router.get("/{name}")
def api_get_image(name: str):
    img = image_manager.get_image(name)
    if img is None:
        raise ServiceError(
            f"image '{name}' not found", code="IMAGE_NOT_FOUND", http_status=404
        )
    return {"status": "ok", "image": img.model_dump()}


@router.delete("/{name}")
def api_delete_image(name: str):
    image_manager.delete_image(name)
    return {"status": "ok", "message": f"image '{name}' deleted"}


@router.post("/upload")
def api_upload_image(
    file: UploadFile = File(...),
    name: str = Form(None),
):
    image_dir = _get_image_dir()
    os.makedirs(image_dir, exist_ok=True)

    fname = name or file.filename
    if not fname:
        raise ServiceError("file name is required", code="INVALID_REQUEST", http_status=400)

    dest = os.path.join(image_dir, fname)
    if os.path.exists(dest):
        raise ServiceError(
            f"image '{fname}' already exists", code="IMAGE_ALREADY_EXISTS", http_status=409
        )

    try:
        content = file.file.read()
        with open(dest, "wb") as f:
            f.write(content)
        logger.info("Uploaded image: %s (%d bytes)", dest, len(content))
    except Exception as e:
        raise ServiceError(f"upload failed: {e}", code="UPLOAD_FAILED", http_status=500)

    img = image_manager.get_image(fname)
    if img:
        return {"status": "ok", "image": img.model_dump()}
    return {"status": "ok", "message": f"file '{fname}' uploaded"}


@router.post("/download")
def api_download_image(url: str = Form(...), name: str = Form(None)):
    image_dir = _get_image_dir()
    os.makedirs(image_dir, exist_ok=True)

    fname = name or os.path.basename(urlparse(url).path)
    if not fname:
        raise ServiceError("could not determine filename", code="INVALID_REQUEST", http_status=400)

    dest = os.path.join(image_dir, fname)
    if os.path.exists(dest):
        raise ServiceError(
            f"file '{fname}' already exists", code="IMAGE_ALREADY_EXISTS", http_status=409
        )

    try:
        logger.info("Downloading %s -> %s", url, dest)
        subprocess.check_call(["curl", "-L", "-o", dest, url], timeout=600)
        logger.info("Downloaded: %s", dest)
    except subprocess.TimeoutExpired:
        raise ServiceError("download timed out", code="DOWNLOAD_TIMEOUT", http_status=500)
    except Exception as e:
        if os.path.exists(dest):
            os.remove(dest)
        raise ServiceError(f"download failed: {e}", code="DOWNLOAD_FAILED", http_status=500)

    img = image_manager.get_image(fname)
    if img:
        return {"status": "ok", "image": img.model_dump()}
    return {"status": "ok", "message": f"'{fname}' downloaded"}


@router.get("/storage/info")
def api_storage_info():
    image_dir = _get_image_dir()
    try:
        import shutil
        usage = shutil.disk_usage(image_dir)
        return {
            "status": "ok",
            "storage": {
                "path": image_dir,
                "total_gb": round(usage.total / (1024**3), 1),
                "used_gb": round(usage.used / (1024**3), 1),
                "free_gb": round(usage.free / (1024**3), 1),
            },
        }
    except Exception as e:
        raise ServiceError(
            f"failed to get storage info: {e}", code="STORAGE_ERROR", http_status=500
        )
