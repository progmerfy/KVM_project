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
        "url": "https://releases.ubuntu.com/24.04/ubuntu-24.04.4-live-server-amd64.iso",
        "description": "Ubuntu Server 24.04.4 LTS ISO",
        "family": "debian",
    },
    "ubuntu-22.04-server": {
        "url": "https://releases.ubuntu.com/22.04/ubuntu-22.04.5-live-server-amd64.iso",
        "description": "Ubuntu Server 22.04.5 LTS ISO",
        "family": "debian",
    },
    "debian-13-netinst": {
        "url": "https://cdimage.debian.org/debian-cd/current/amd64/iso-cd/debian-13.5.0-amd64-netinst.iso",
        "description": "Debian 13 Trixie Net Install ISO",
        "family": "debian",
    },
    "fedora-41-server": {
        "url": "https://download.fedoraproject.org/pub/fedora/linux/releases/41/Server/x86_64/iso/Fedora-Server-dvd-x86_64-41-1.4.iso",
        "description": "Fedora 41 Server DVD ISO",
        "family": "rhel",
    },
    "centos-stream-9-iso": {
        "url": "https://mirror.rackspace.com/centos-stream/9-stream/BaseOS/x86_64/iso/CentOS-Stream-9-latest-x86_64-dvd1.iso",
        "description": "CentOS Stream 9 DVD ISO",
        "family": "rhel",
    },
    "rocky-9-iso": {
        "url": "https://dl.rockylinux.org/pub/rocky/9/isos/x86_64/Rocky-9-latest-x86_64-minimal.iso",
        "description": "Rocky Linux 9 Minimal ISO",
        "family": "rhel",
    },
    "freebsd-14.4-iso": {
        "url": "https://download.freebsd.org/releases/ISO-IMAGES/14.4/FreeBSD-14.4-RELEASE-amd64-disc1.iso",
        "description": "FreeBSD 14.4-RELEASE amd64",
        "family": "freebsd",
    },
    "freebsd-13.5-iso": {
        "url": "https://download.freebsd.org/releases/ISO-IMAGES/13.5/FreeBSD-13.5-RELEASE-amd64-disc1.iso",
        "description": "FreeBSD 13.5-RELEASE amd64",
        "family": "freebsd",
    },
    "opensuse-leap-15.6-iso": {
        "url": "https://download.opensuse.org/distribution/leap/15.6/iso/openSUSE-Leap-15.6-DVD-x86_64-Current.iso",
        "description": "openSUSE Leap 15.6 DVD",
        "family": "suse",
    },
    "opensuse-tumbleweed-iso": {
        "url": "https://download.opensuse.org/tumbleweed/iso/openSUSE-Tumbleweed-DVD-x86_64-Current.iso",
        "description": "openSUSE Tumbleweed DVD",
        "family": "suse",
    },
    "alpine-3.20-iso": {
        "url": "https://dl-cdn.alpinelinux.org/alpine/v3.20/releases/x86_64/alpine-standard-3.20.3-x86_64.iso",
        "description": "Alpine Linux 3.20 Standard",
        "family": "alpine",
    },
    "astra-orel-2.12": {
        "url": "https://download.astralinux.ru/astra/stable/orel/iso/orel-current.iso",
        "description": "Astra Linux Common Edition (Orel) 2.12 — ALCE",
        "family": "astra",
    },
    "redos-8.0": {
        "url": "https://files.red-soft.ru/redos/8.0/x86_64/iso/redos-8-20250711.4-Everything-x86_64-DVD1.iso",
        "description": "RED OS 8.0 x86_64 (Server/Workstation)",
        "family": "redos",
    },
    "redos-7.3": {
        "url": "https://files.red-soft.ru/redos/7.3/x86_64/iso/redos-MUROM-7.3.6-20250715.0-Everything-x86_64-DVD1.iso",
        "description": "RED OS 7.3 MUROM x86_64",
        "family": "redos",
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
    "freebsd-14.1": {
        "url": "https://download.freebsd.org/releases/VM-IMAGES/14.1-RELEASE/amd64/Latest/FreeBSD-14.1-RELEASE-amd64.zfs.qcow2",
        "description": "FreeBSD 14.1-RELEASE ZFS",
        "family": "freebsd",
    },
    "freebsd-13.4": {
        "url": "https://download.freebsd.org/releases/VM-IMAGES/13.4-RELEASE/amd64/Latest/FreeBSD-13.4-RELEASE-amd64.qcow2",
        "description": "FreeBSD 13.4-RELEASE UFS",
        "family": "freebsd",
    },
    "opensuse-leap-15.6": {
        "url": "https://download.opensuse.org/repositories/cloud:/images:/openSUSE-Leap/images/openSUSE-Leap-15.6-SLES.x86_64-NoCloud.qcow2",
        "description": "openSUSE Leap 15.6 NoCloud",
        "family": "suse",
    },
    "opensuse-tumbleweed": {
        "url": "https://download.opensuse.org/repositories/cloud:/images:/openSUSE-Tumbleweed/images/openSUSE-Tumbleweed-NoCloud.x86_64.qcow2",
        "description": "openSUSE Tumbleweed NoCloud",
        "family": "suse",
    },
    "alpine-3.20": {
        "url": "https://dl-cdn.alpinelinux.org/alpine/v3.20/releases/x86_64/alpine-virt-3.20.3-x86_64.qcow2",
        "description": "Alpine Linux 3.20 virt",
        "family": "alpine",
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
        info = _get_image_info(dest)
        if info:
            logger.info("Cloud image already exists: %s", dest)
            return info
        else:
            logger.warning("Removing stale 0-byte cloud image: %s", dest)
            os.remove(dest)

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
        info = _get_image_info(dest)
        if info:
            logger.info("ISO already exists: %s", dest)
            return info
        else:
            logger.warning("Removing stale 0-byte ISO: %s", dest)
            os.remove(dest)

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
        st = os.stat(fpath)
        return ImageInfo(
            name=os.path.basename(fpath),
            path=fpath,
            format=data.get("format", "unknown"),
            virtual_size_gb=round(data.get("virtual-size", 0) / (1024**3), 2),
            actual_size_bytes=st.st_size,
            backing_file=data.get("backing-filename"),
            mtime=st.st_mtime,
            ctime=st.st_ctime,
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
