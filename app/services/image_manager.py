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
ISO_REPO = {
    "ubuntu-24.04-server": {
        "url": "https://releases.ubuntu.com/24.04/ubuntu-24.04.1-live-server-amd64.iso",
        "description": "Ubuntu Server 24.04 LTS ISO",
        "family": "debian",
    },
    "ubuntu-22.04-server": {
        "url": "https://releases.ubuntu.com/22.04/ubuntu-22.04.5-live-server-amd64.iso",
        "description": "Ubuntu Server 22.04 LTS ISO",
        "family": "debian",
    },
    "debian-12-netinst": {
        "url": "https://cdimage.debian.org/debian-cd/current/amd64/iso-cd/debian-12.10.0-amd64-netinst.iso",
        "description": "Debian 12 Bookworm Net Install ISO",
        "family": "debian",
    },
    "fedora-41-server": {
        "url": "https://download.fedoraproject.org/pub/fedora/linux/releases/41/Server/x86_64/iso/Fedora-Server-dvd-x86_64-41-1.4.iso",
        "description": "Fedora 41 Server DVD ISO",
        "family": "rhel",
    },
    "centos-stream-9-iso": {
        "url": "https://mirror.bytemark.co.uk/centos-stream/9-stream/BaseOS/x86_64/iso/CentOS-Stream-9-latest-x86_64-dvd1.iso",
        "description": "CentOS Stream 9 DVD ISO",
        "family": "rhel",
    },
    "rocky-9-iso": {
        "url": "https://dl.rockylinux.org/pub/rocky/9/isos/x86_64/Rocky-9.5-x86_64-minimal.iso",
        "description": "Rocky Linux 9 Minimal ISO",
        "family": "rhel",
    },
}

CLOUD_IMAGES = {
    "ubuntu-24.04": {
        "url": "https://cloud-images.ubuntu.com/noble/current/noble-server-cloudimg-amd64.img",
        "description": "Ubuntu Server 24.04 LTS (Noble)",
        "family": "debian",
    },
    "ubuntu-22.04": {
        "url": "https://cloud-images.ubuntu.com/jammy/current/jammy-server-cloudimg-amd64.img",
        "description": "Ubuntu Server 22.04 LTS (Jammy)",
        "family": "debian",
    },
    "ubuntu-20.04": {
        "url": "https://cloud-images.ubuntu.com/focal/current/focal-server-cloudimg-amd64.img",
        "description": "Ubuntu Server 20.04 LTS (Focal)",
        "family": "debian",
    },
    "debian-12": {
        "url": "https://cloud.debian.org/images/cloud/bookworm/latest/debian-12-generic-amd64.qcow2",
        "description": "Debian 12 (Bookworm)",
        "family": "debian",
    },
    "debian-11": {
        "url": "https://cloud.debian.org/images/cloud/bullseye/latest/debian-11-generic-amd64.qcow2",
        "description": "Debian 11 (Bullseye)",
        "family": "debian",
    },
    "fedora-40": {
        "url": "https://download.fedoraproject.org/pub/fedora/linux/releases/40/Cloud/x86_64/images/Fedora-Cloud-Base-40-1.14.x86_64.qcow2",
        "description": "Fedora 40 Cloud",
        "family": "rhel",
    },
    "fedora-39": {
        "url": "https://download.fedoraproject.org/pub/fedora/linux/releases/39/Cloud/x86_64/images/Fedora-Cloud-Base-39-1.5.x86_64.qcow2",
        "description": "Fedora 39 Cloud",
        "family": "rhel",
    },
    "centos-stream-9": {
        "url": "https://cloud.centos.org/centos/9-stream/x86_64/images/CentOS-Stream-GenericCloud-9-latest.x86_64.qcow2",
        "description": "CentOS Stream 9",
        "family": "rhel",
    },
    "centos-stream-8": {
        "url": "https://cloud.centos.org/centos/8-stream/x86_64/images/CentOS-Stream-GenericCloud-8-latest.x86_64.qcow2",
        "description": "CentOS Stream 8",
        "family": "rhel",
    },
    "rocky-9": {
        "url": "https://dl.rockylinux.org/pub/rocky/9/images/x86_64/Rocky-9-GenericCloud.latest.x86_64.qcow2",
        "description": "Rocky Linux 9",
        "family": "rhel",
    },
    "rocky-8": {
        "url": "https://dl.rockylinux.org/pub/rocky/8/images/x86_64/Rocky-8-GenericCloud.latest.x86_64.qcow2",
        "description": "Rocky Linux 8",
        "family": "rhel",
    },
    "almalinux-9": {
        "url": "https://repo.almalinux.org/almalinux/9/cloud/x86_64/images/AlmaLinux-9-GenericCloud-latest.x86_64.qcow2",
        "description": "AlmaLinux 9",
        "family": "rhel",
    },
    "almalinux-8": {
        "url": "https://repo.almalinux.org/almalinux/8/cloud/x86_64/images/AlmaLinux-8-GenericCloud-latest.x86_64.qcow2",
        "description": "AlmaLinux 8",
        "family": "rhel",
    },
    "arch": {
        "url": "https://geo.mirror.pkgbuild.com/images/latest/Arch-Linux-x86_64-cloudimg.qcow2",
        "description": "Arch Linux Cloud",
        "family": "arch",
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


def download_repo_iso(name: str) -> ImageInfo:
    if name not in ISO_REPO:
        raise ServiceError(
            f"unknown repo ISO '{name}'. Available: {list(ISO_REPO.keys())}",
            code="REPO_ISO_NOT_FOUND",
            http_status=404,
        )

    image_dir = _get_image_dir()
    ri = ISO_REPO[name]
    filename = os.path.basename(ri["url"])
    dest = os.path.join(image_dir, filename)

    if os.path.isfile(dest):
        logger.info("ISO already exists: %s", dest)
        info = _get_image_info(dest)
        if info:
            return info

    logger.info("Downloading repo ISO %s from %s", name, ri["url"])
    try:
        subprocess.check_call(
            ["curl", "-L", "-o", dest, ri["url"]],
            timeout=600,
        )
        logger.info("Downloaded repo ISO: %s", dest)
    except Exception as e:
        raise ServiceError(
            f"failed to download repo ISO '{name}': {e}",
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


def list_repo_images() -> dict:
    families = {}
    for name, info in CLOUD_IMAGES.items():
        fam = info.get("family", "other")
        if fam not in families:
            families[fam] = []
        families[fam].append({
            "name": name,
            "url": info["url"],
            "description": info["description"],
            "type": "cloud",
            "is_iso": False,
        })
    for name, info in ISO_REPO.items():
        fam = info.get("family", "other")
        if fam not in families:
            families[fam] = []
        families[fam].append({
            "name": name,
            "url": info["url"],
            "description": info["description"],
            "type": "iso",
            "is_iso": True,
        })
    return families
