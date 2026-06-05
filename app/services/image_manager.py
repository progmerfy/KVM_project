import logging
import os
import subprocess
import json
from typing import Optional

from app.config import settings
from app.errors import ServiceError
from app.models.image import ImageInfo

logger = logging.getLogger(__name__)

SUPPORTED_EXTENSIONS = {".qcow2", ".img", ".iso", ".raw"}
CLOUD_IMAGES = {
    "ubuntu-24.04": {
        "url": "https://cloud-images.ubuntu.com/noble/current/noble-server-cloudimg-amd64.img",
        "description": "Ubuntu Server 24.04 LTS (Noble) cloud image",
    },
    "ubuntu-22.04": {
        "url": "https://cloud-images.ubuntu.com/jammy/current/jammy-server-cloudimg-amd64.img",
        "description": "Ubuntu Server 22.04 LTS (Jammy) cloud image",
    },
    "debian-12": {
        "url": "https://cloud.debian.org/images/cloud/bookworm/latest/debian-12-generic-amd64.qcow2",
        "description": "Debian 12 (Bookworm) cloud image",
    },
}


def _get_image_dir() -> str:
    return settings.storage_pool or "/var/lib/libvirt/images"


def list_images() -> list[ImageInfo]:
    image_dir = _get_image_dir()
    if not os.path.isdir(image_dir):
        return []

    result = []
    for fname in sorted(os.listdir(image_dir)):
        fpath = os.path.join(image_dir, fname)
        if not os.path.isfile(fpath):
            continue
        ext = os.path.splitext(fname)[1].lower()
        if ext not in SUPPORTED_EXTENSIONS:
            continue
        info = _get_image_info(fpath)
        if info:
            result.append(info)
    return result


def get_image(name: str) -> Optional[ImageInfo]:
    image_dir = _get_image_dir()
    fpath = os.path.join(image_dir, name)
    if not os.path.isfile(fpath):
        return None
    return _get_image_info(fpath)


def delete_image(name: str) -> None:
    image_dir = _get_image_dir()
    fpath = os.path.join(image_dir, name)
    if not os.path.isfile(fpath):
        raise ServiceError(f"image '{name}' not found", code="IMAGE_NOT_FOUND", http_status=404)
    os.remove(fpath)
    logger.info("Deleted image: %s", fpath)


def download_cloud_image(name: str) -> ImageInfo:
    if name not in CLOUD_IMAGES:
        raise ServiceError(
            f"unknown cloud image '{name}'. Available: {list(CLOUD_IMAGES.keys())}",
            code="CLOUD_IMAGE_NOT_FOUND",
            http_status=404,
        )

    image_dir = _get_image_dir()
    ci = CLOUD_IMAGES[name]
    filename = os.path.basename(ci["url"])
    dest = os.path.join(image_dir, filename)

    if os.path.isfile(dest):
        logger.info("Cloud image already exists: %s", dest)
        info = _get_image_info(dest)
        if info:
            return info

    logger.info("Downloading cloud image %s from %s", name, ci["url"])
    try:
        subprocess.check_call(
            ["curl", "-L", "-o", dest, ci["url"]],
            timeout=600,
        )
        logger.info("Downloaded cloud image: %s", dest)
    except Exception as e:
        raise ServiceError(
            f"failed to download cloud image '{name}': {e}",
            code="DOWNLOAD_FAILED",
            http_status=500,
        )

    info = _get_image_info(dest)
    if not info:
        raise ServiceError(
            f"downloaded file is not a valid image: {dest}",
            code="INVALID_IMAGE",
            http_status=500,
        )
    return info


def _get_image_info(fpath: str) -> Optional[ImageInfo]:
    try:
        output = subprocess.check_output(
            ["qemu-img", "info", "--output", "json", fpath],
            stderr=subprocess.DEVNULL,
        )
        data = json.loads(output)
        return ImageInfo(
            name=os.path.basename(fpath),
            path=fpath,
            format=data.get("format", "unknown"),
            virtual_size_gb=round(data.get("virtual-size", 0) / (1024**3), 2),
            actual_size_bytes=os.path.getsize(fpath),
            backing_file=data.get("backing-filename"),
        )
    except Exception as e:
        logger.warning("Failed to get image info for %s: %s", fpath, e)
        return None


def list_cloud_images() -> dict:
    return {
        name: {"url": info["url"], "description": info["description"]}
        for name, info in CLOUD_IMAGES.items()
    }
