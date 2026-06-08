import os
import shutil
import subprocess
import logging

logger = logging.getLogger(__name__)


def create_blank_disk(vm_name: str, size_gb: int, dest_dir: str = "/var/lib/libvirt/images") -> str:
    os.makedirs(dest_dir, exist_ok=True)
    target = os.path.join(dest_dir, f"{vm_name}.qcow2")

    if os.path.exists(target):
        raise FileExistsError(f"target disk already exists: {target}")

    subprocess.check_call([
        "qemu-img", "create", "-f", "qcow2", target, f"{size_gb}G"
    ])
    logger.info("Created blank qcow2 disk: %s (%dG)", target, size_gb)
    return target


def prepare_disk(base_image: str, vm_name: str, size_gb: int) -> str:
    """Create a qcow2 copy based on base_image next to base_image.

    Returns path to new disk.
    """
    if not os.path.exists(base_image):
        raise FileNotFoundError(f"base image not found: {base_image}")

    dest_dir = os.path.dirname(base_image)
    target = os.path.join(dest_dir, f"{vm_name}.qcow2")

    if os.path.exists(target):
        raise FileExistsError(f"target disk already exists: {target}")

    try:
        subprocess.check_call([
            "qemu-img", "create", "-f", "qcow2", "-b", base_image, target, f"{size_gb}G"
        ])
        logger.info("Created qcow2 disk via qemu-img: %s", target)
    except Exception:
        logger.warning("qemu-img failed, falling back to copy from %s", base_image)
        shutil.copy(base_image, target)
        logger.info("Copied base image to: %s", target)

    return target


def remove_disk(disk_path: str) -> None:
    """Remove a disk file. Used for rollback."""
    if disk_path and os.path.exists(disk_path):
        os.remove(disk_path)
        logger.info("Removed disk: %s", disk_path)
