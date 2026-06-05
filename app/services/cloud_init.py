import logging
import os
import subprocess
import tempfile
from typing import Optional

from app.config import settings

logger = logging.getLogger(__name__)


def build_cloudinit_iso(
    vm_name: str,
    ssh_public_key: Optional[str] = None,
    username: str = "user",
    hostname: Optional[str] = None,
    user_data_raw: Optional[str] = None,
    network_config: Optional[str] = None,
    root_password: Optional[str] = None,
) -> str:
    """Generate a cloud-init ISO and return the path to it."""
    hostname = hostname or vm_name

    with tempfile.TemporaryDirectory(prefix=f"cloudinit-{vm_name}-") as tmpdir:
        meta_data = f"""instance-id: {vm_name}
local-hostname: {hostname}
"""

        _pw = ""
        if root_password:
            _pw = f"""
chpasswd:
  list: |
    root:{root_password}
  expire: False
ssh_pwauth: true
"""

        if user_data_raw:
            user_data = user_data_raw + _pw
        elif ssh_public_key:
            user_data = f"""#cloud-config
users:
  - name: {username}
    sudo: ALL=(ALL) NOPASSWD:ALL
    lock_passwd: true
    ssh_authorized_keys:
      - {ssh_public_key}
    shell: /bin/bash
ssh_authorized_keys:
  - {ssh_public_key}
package_update: true
package_upgrade: false
hostname: {hostname}
manage_etc_hosts: true
{_pw}"""
        else:
            user_data = f"""#cloud-config
hostname: {hostname}
manage_etc_hosts: true
{_pw}"""

        os.makedirs(tmpdir, exist_ok=True)
        (tmpdir_path := tmpdir)

        with open(os.path.join(tmpdir_path, "meta-data"), "w") as f:
            f.write(meta_data)
        with open(os.path.join(tmpdir_path, "user-data"), "w") as f:
            f.write(user_data)
        if network_config:
            with open(os.path.join(tmpdir_path, "network-config"), "w") as f:
                f.write(network_config)

        ci_dir = _get_cloudinit_dir()
        os.makedirs(ci_dir, exist_ok=True)
        iso_path = os.path.join(ci_dir, f"{vm_name}-cloudinit.iso")

        try:
            subprocess.check_call(
                [
                    "genisoimage",
                    "-output", iso_path,
                    "-volid", "cidata",
                    "-joliet",
                    "-rock",
                    os.path.join(tmpdir_path, "meta-data"),
                    os.path.join(tmpdir_path, "user-data"),
                ]
                + ([os.path.join(tmpdir_path, "network-config")] if network_config else []),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            logger.info("Cloud-init ISO created: %s", iso_path)
        except Exception as e:
            logger.error("Failed to create cloud-init ISO: %s", e)
            raise

    return iso_path


def cleanup_cloudinit_iso(vm_name: str) -> None:
    ci_dir = _get_cloudinit_dir()
    iso_path = os.path.join(ci_dir, f"{vm_name}-cloudinit.iso")
    if os.path.exists(iso_path):
        os.remove(iso_path)
        logger.info("Cleaned up cloud-init ISO: %s", iso_path)


def _get_cloudinit_dir() -> str:
    base = settings.storage_pool or "/var/lib/libvirt/images"
    ci_dir = os.path.join(base, "cloudinit")
    os.makedirs(ci_dir, exist_ok=True)
    return ci_dir
