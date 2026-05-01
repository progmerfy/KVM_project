import os
import shutil
import subprocess
from typing import Optional


def prepare_disk(base_image: str, vm_name: str, size_gb: int) -> str:
    """Create a qcow2 copy based on base_image next to base_image.

    Returns path to new disk.
    """
    if not os.path.exists(base_image):
        raise FileNotFoundError(f"base image not found: {base_image}")

    dest_dir = os.path.dirname(base_image)
    target = os.path.join(dest_dir, f"{vm_name}.qcow2")

    # try fast clone via qemu-img if available
    try:
        subprocess.check_call(["qemu-img", "create", "-f", "qcow2", "-b", base_image, target, f"{size_gb}G"])  # type: ignore
    except Exception:
        # fallback to simple copy
        shutil.copy(base_image, target)

    return target
