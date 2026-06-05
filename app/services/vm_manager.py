import logging
import html
import secrets
import string
from pathlib import Path
from typing import Optional

from app.api.schemas import VMCreateRequest, VMActionRequest, VMISORequest, VMResizeRequest
from app.infrastructure import libvirt_driver, storage, network
from app.errors import ServiceError
from app.models.vm_spec import VMSpec
from app.config import settings
from app.services import cloud_init

logger = logging.getLogger(__name__)


def create_vm(req: VMCreateRequest) -> dict:
    host = req.host_uri or settings.default_host_uri
    spec = VMSpec(
        name=req.name,
        cpu=req.cpu,
        memory_mb=req.memory_mb,
        disk_gb=req.disk_gb,
        image=req.image,
        iso_path=req.iso_path,
        network=req.network or "default",
    )

    disk_path = None
    cloud_init_iso_path = None
    root_password: Optional[str] = None
    try:
        disk_path = storage.prepare_disk(spec.image, spec.name, spec.disk_gb)
        spec.disk_path = disk_path

        if req.cloud_init_user_data or req.cloud_init_ssh_key:
            if req.root_password:
                root_password = req.root_password
            else:
                root_password = "".join(
                    secrets.choice(string.ascii_letters + string.digits)
                    for _ in range(8)
                )
            cloud_init_iso_path = cloud_init.build_cloudinit_iso(
                vm_name=req.name,
                ssh_public_key=req.cloud_init_ssh_key,
                username=req.cloud_init_user,
                user_data_raw=req.cloud_init_user_data,
                root_password=root_password,
            )
            spec.cloud_init_iso = cloud_init_iso_path
    except FileNotFoundError as e:
        raise ServiceError(str(e), code="IMAGE_NOT_FOUND", http_status=400)
    except FileExistsError as e:
        raise ServiceError(str(e), code="DISK_ALREADY_EXISTS", http_status=409)
    except Exception as e:
        raise ServiceError(f"storage error: {e}", code="STORAGE_ERROR", http_status=500)

    conn = None
    try:
        conn = libvirt_driver.connect(host)

        network_info = network.ensure_default_network(conn)
        logger.info("Network ready: %s", network_info)

        xml = _render_domain_xml(spec)
        logger.info("Creating VM '%s' on host %s", spec.name, host)

        domain = libvirt_driver.define_vm(conn, xml)
        libvirt_driver.start_vm(conn, domain)
        logger.info("VM '%s' created and started", spec.name)

        ip = network.get_vm_ip(conn, spec.name)
        result = {
            "name": spec.name,
            "domain": domain,
            "ip_address": ip,
            "network": spec.network,
            "cloud_init": bool(cloud_init_iso_path),
        }
        if root_password:
            result["root_password"] = root_password
        return result
    except Exception:
        if disk_path:
            storage.remove_disk(disk_path)
        if cloud_init_iso_path:
            try:
                cloud_init.cleanup_cloudinit_iso(spec.name)
            except Exception:
                pass
        raise
    finally:
        if conn is not None:
            libvirt_driver.close(conn)


def start_vm(req: VMActionRequest) -> None:
    host = req.host_uri or settings.default_host_uri
    conn = libvirt_driver.connect(host)
    try:
        libvirt_driver.start_vm(conn, req.name)
        logger.info("VM '%s' started", req.name)
    finally:
        if conn is not None:
            libvirt_driver.close(conn)


def stop_vm(req: VMActionRequest) -> None:
    host = req.host_uri or settings.default_host_uri
    conn = libvirt_driver.connect(host)
    try:
        libvirt_driver.stop_vm(conn, req.name)
        logger.info("VM '%s' stopped", req.name)
    finally:
        if conn is not None:
            libvirt_driver.close(conn)


def reboot_vm(req: VMActionRequest) -> None:
    host = req.host_uri or settings.default_host_uri
    conn = libvirt_driver.connect(host)
    try:
        libvirt_driver.reboot_vm(conn, req.name)
        logger.info("VM '%s' rebooted", req.name)
    finally:
        if conn is not None:
            libvirt_driver.close(conn)


def reset_vm(req: VMActionRequest) -> None:
    host = req.host_uri or settings.default_host_uri
    conn = libvirt_driver.connect(host)
    try:
        libvirt_driver.reset_vm(conn, req.name)
        logger.info("VM '%s' force-reset", req.name)
    finally:
        if conn is not None:
            libvirt_driver.close(conn)


def delete_vm(req: VMActionRequest) -> None:
    host = req.host_uri or settings.default_host_uri
    conn = libvirt_driver.connect(host)
    logger.info("Deleting VM '%s' on host %s", req.name, host)
    try:
        libvirt_driver.stop_vm(conn, req.name)
    except Exception:
        logger.exception("Error stopping VM '%s' before undefine", req.name)
    try:
        libvirt_driver.undefine_vm(conn, req.name, remove_storage=True)
        logger.info("VM '%s' deleted", req.name)
    finally:
        if conn is not None:
            libvirt_driver.close(conn)
    try:
        cloud_init.cleanup_cloudinit_iso(req.name)
    except Exception:
        pass


def get_vm_status(name: str, host_uri: str = None) -> str:
    host = host_uri or settings.default_host_uri
    conn = libvirt_driver.connect(host)
    try:
        try:
            dom = conn.lookupByName(name)
        except Exception:
            return "not-found"
        active = dom.isActive()
        return "running" if active == 1 else "stopped"
    finally:
        if conn is not None:
            libvirt_driver.close(conn)


def get_vm_info(name: str, host_uri: str = None) -> Optional[dict]:
    host = host_uri or settings.default_host_uri
    conn = libvirt_driver.connect(host)
    try:
        try:
            dom = conn.lookupByName(name)
        except Exception:
            return None
        active = dom.isActive()
        state = "running" if active == 1 else "stopped"
        ip = network.get_vm_ip(conn, name) if active == 1 else None

        xml = libvirt_driver.get_domain_xml(conn, name, 0)
        info = {
            "name": name,
            "state": state,
            "ip_address": ip,
        }
        if xml:
            import re
            m = re.search(r"<memory unit='MiB'>(\d+)</memory>", xml)
            if m:
                info["memory_mb"] = int(m.group(1))
            else:
                m = re.search(r"<memory unit='KiB'>(\d+)</memory>", xml)
                if m:
                    info["memory_mb"] = int(m.group(1)) // 1024
            m = re.search(r"<vcpu(?: placement='static')?>(\d+)</vcpu>", xml)
            if m:
                info["cpu"] = int(m.group(1))
        return info
    finally:
        if conn is not None:
            libvirt_driver.close(conn)


def _get_disk_target(conn, name: str) -> Optional[str]:
    """Find the first disk device target (e.g. 'vda') from domain XML."""
    try:
        xml = libvirt_driver.get_domain_xml(conn, name)
        if not xml:
            return None
        import re
        m = re.search(
            r"<disk type='file' device='disk'>.*?<target dev='([^']+)'",
            xml, re.DOTALL,
        )
        return m.group(1) if m else None
    except Exception:
        return None


def _get_disk_path(conn, name: str) -> Optional[str]:
    """Find the first disk source file path from domain XML."""
    try:
        xml = libvirt_driver.get_domain_xml(conn, name)
        if not xml:
            return None
        import re
        m = re.search(
            r"<disk type='file' device='disk'>.*?<source file='([^']+)'",
            xml, re.DOTALL,
        )
        return m.group(1) if m else None
    except Exception:
        return None


def resize_vm(req) -> dict:
    host = req.host_uri or settings.default_host_uri
    conn = libvirt_driver.connect(host)
    try:
        dom = conn.lookupByName(req.name)
        was_active = dom.isActive() == 1
        should_restart = was_active
        changes = {}

        if req.cpu is not None or req.memory_mb is not None:
            if was_active:
                try:
                    if req.cpu is not None:
                        libvirt_driver.set_vcpus(conn, req.name, req.cpu)
                        changes["cpu"] = req.cpu
                    if req.memory_mb is not None:
                        libvirt_driver.set_memory(conn, req.name, req.memory_mb * 1024)
                        changes["memory_mb"] = req.memory_mb
                except Exception:
                    libvirt_driver.destroy_vm(conn, req.name)
                    should_restart = True

            if req.cpu is not None and "cpu" not in changes:
                xml = libvirt_driver.get_domain_xml(conn, req.name, 1)
                import re
                xml = re.sub(
                    r"<vcpu[^>]*>.*?</vcpu>",
                    f"<vcpu placement='static'>{req.cpu}</vcpu>",
                    xml,
                )
                libvirt_driver.redefine_domain(conn, req.name, xml)
                changes["cpu"] = req.cpu

            if req.memory_mb is not None and "memory_mb" not in changes:
                xml = libvirt_driver.get_domain_xml(conn, req.name, 1)
                import re
                xml = re.sub(
                    r"<memory[^>]*>.*?</memory>",
                    f"<memory unit='MiB'>{req.memory_mb}</memory>",
                    xml,
                )
                xml = re.sub(
                    r"<currentMemory[^>]*>.*?</currentMemory>",
                    f"<currentMemory unit='MiB'>{req.memory_mb}</currentMemory>",
                    xml,
                )
                libvirt_driver.redefine_domain(conn, req.name, xml)
                changes["memory_mb"] = req.memory_mb

            if should_restart:
                libvirt_driver.start_vm(conn, req.name)

        if req.disk_gb is not None:
            disk_path = _get_disk_path(conn, req.name)
            target = _get_disk_target(conn, req.name)
            if disk_path and target:
                import subprocess
                subprocess.check_call(
                    ["qemu-img", "resize", disk_path, f"{req.disk_gb}G"],
                    stdout=subprocess.DEVNULL,
                )
                libvirt_driver.block_resize(conn, req.name, target, req.disk_gb * 1024**3 // 512)
                changes["disk_gb"] = req.disk_gb

        return changes
    finally:
        if conn is not None:
            libvirt_driver.close(conn)


def attach_disk(name: str, size_gb: int, target_dev: str = "vdb", host_uri: str = None) -> dict:
    host = host_uri or settings.default_host_uri
    conn = libvirt_driver.connect(host)
    try:
        images_dir = Path(settings.storage_pool)
        images_dir.mkdir(parents=True, exist_ok=True)
        disk_path = str(images_dir / f"{name}_{target_dev}.qcow2")
        libvirt_driver.create_disk(disk_path, size_gb)
        libvirt_driver.attach_disk(conn, name, disk_path, target_dev)
        return {"name": name, "disk_path": disk_path, "target_dev": target_dev}
    finally:
        if conn is not None:
            libvirt_driver.close(conn)


def detach_disk_vm(name: str, target_dev: str, host_uri: str = None) -> dict:
    host = host_uri or settings.default_host_uri
    conn = libvirt_driver.connect(host)
    try:
        libvirt_driver.detach_disk(conn, name, target_dev)
        return {"name": name, "target_dev": target_dev}
    finally:
        if conn is not None:
            libvirt_driver.close(conn)


def snapshot_create(name: str, snap_name: str, host_uri: str = None) -> dict:
    host = host_uri or settings.default_host_uri
    conn = libvirt_driver.connect(host)
    try:
        libvirt_driver.snapshot_create(conn, name, snap_name)
        return {"name": name, "snapshot": snap_name}
    finally:
        if conn is not None:
            libvirt_driver.close(conn)


def snapshot_list(name: str, host_uri: str = None) -> list:
    host = host_uri or settings.default_host_uri
    conn = libvirt_driver.connect(host)
    try:
        return libvirt_driver.snapshot_list(conn, name)
    finally:
        if conn is not None:
            libvirt_driver.close(conn)


def snapshot_revert(name: str, snap_name: str, host_uri: str = None) -> dict:
    host = host_uri or settings.default_host_uri
    conn = libvirt_driver.connect(host)
    try:
        libvirt_driver.snapshot_revert(conn, name, snap_name)
        return {"name": name, "snapshot": snap_name}
    finally:
        if conn is not None:
            libvirt_driver.close(conn)


def snapshot_delete(name: str, snap_name: str, host_uri: str = None) -> dict:
    host = host_uri or settings.default_host_uri
    conn = libvirt_driver.connect(host)
    try:
        libvirt_driver.snapshot_delete(conn, name, snap_name)
        return {"name": name, "snapshot": snap_name}
    finally:
        if conn is not None:
            libvirt_driver.close(conn)


def export_vm(name: str, host_uri: str = None) -> dict:
    host = host_uri or settings.default_host_uri
    conn = libvirt_driver.connect(host)
    try:
        xml = libvirt_driver.get_domain_xml(conn, name)
        disk_paths = [_get_disk_path(conn, name)] if _get_disk_path(conn, name) else []
        return {
            "name": name,
            "xml": xml,
            "disks": disk_paths,
        }
    finally:
        if conn is not None:
            libvirt_driver.close(conn)


def import_vm(xml: str, disk_paths: list[str] = None, host_uri: str = None) -> dict:
    host = host_uri or settings.default_host_uri
    conn = libvirt_driver.connect(host)
    try:
        libvirt_driver.define_vm(conn, xml)
        name_match = __import__("re").search(r"<name>([^<]+)</name>", xml)
        vm_name = name_match.group(1) if name_match else "unknown"
        logger.info("Imported VM '%s' from XML definition", vm_name)
        return {"name": vm_name}
    finally:
        if conn is not None:
            libvirt_driver.close(conn)


def clone_vm(name: str, new_name: str, host_uri: str = None) -> dict:
    host = host_uri or settings.default_host_uri
    conn = libvirt_driver.connect(host)
    try:
        xml = libvirt_driver.get_domain_xml(conn, name)
        new_xml = libvirt_driver.rename_in_xml(xml, new_name)

        src_disk = _get_disk_path(conn, name)
        dst_disk = None
        if src_disk:
            dst_disk = str(Path(src_disk).parent / f"{new_name}.qcow2")
            libvirt_driver.copy_disk_image(src_disk, dst_disk)
            new_xml = new_xml.replace(src_disk, dst_disk)

        libvirt_driver.define_vm(conn, new_xml)
        libvirt_driver.start_vm(conn, new_name)
        ip = network.get_vm_ip(conn, new_name)
        return {"name": new_name, "ip_address": ip, "disk": dst_disk}
    finally:
        if conn is not None:
            libvirt_driver.close(conn)


def backup_vm(name: str, host_uri: str = None) -> dict:
    from datetime import datetime
    host = host_uri or settings.default_host_uri
    conn = libvirt_driver.connect(host)
    try:
        xml = libvirt_driver.get_domain_xml(conn, name)
        src_disk = _get_disk_path(conn, name)

        backup_dir = Path(settings.storage_pool) / "backups" / f"{name}_{datetime.now():%Y%m%d_%H%M%S}"
        backup_dir.mkdir(parents=True, exist_ok=True)

        (backup_dir / f"{name}.xml").write_text(xml)

        disks_backed_up = []
        if src_disk:
            dst = str(backup_dir / Path(src_disk).name)
            libvirt_driver.copy_disk_image(src_disk, dst)
            disks_backed_up.append(dst)

        return {"name": name, "backup_dir": str(backup_dir), "disks": disks_backed_up}
    finally:
        if conn is not None:
            libvirt_driver.close(conn)


def restore_vm(backup_dir: str, new_name: str = None, host_uri: str = None) -> dict:
    host = host_uri or settings.default_host_uri
    conn = libvirt_driver.connect(host)
    try:
        backup_path = Path(backup_dir)
        xml_path = next(backup_path.glob("*.xml"), None)
        if not xml_path:
            raise ServiceError("No XML found in backup directory", code="BACKUP_INVALID", http_status=400)

        xml = xml_path.read_text()
        if new_name:
            xml = libvirt_driver.rename_in_xml(xml, new_name)

        disk_files = list(backup_path.glob("*.qcow2"))
        if disk_files:
            src = str(disk_files[0])
            dst = str(Path(settings.storage_pool) / disk_files[0].name)
            if src != dst:
                libvirt_driver.copy_disk_image(src, dst)
                xml = xml.replace(src, dst)

        vm_name = libvirt_driver.define_vm(conn, xml)
        libvirt_driver.start_vm(conn, vm_name)
        ip = network.get_vm_ip(conn, vm_name)
        return {"name": vm_name, "ip_address": ip}
    finally:
        if conn is not None:
            libvirt_driver.close(conn)


def get_metrics(name: str, host_uri: str = None) -> dict:
    host = host_uri or settings.default_host_uri
    conn = libvirt_driver.connect(host)
    try:
        return libvirt_driver.get_metrics(conn, name)
    finally:
        if conn is not None:
            libvirt_driver.close(conn)


def network_create(name: str, bridge: str, subnet: str, host_uri: str = None) -> dict:
    host = host_uri or settings.default_host_uri
    conn = libvirt_driver.connect(host)
    try:
        libvirt_driver.network_create_nat(conn, name, bridge, subnet)
        return {"name": name, "bridge": bridge, "subnet": subnet}
    finally:
        if conn is not None:
            libvirt_driver.close(conn)


def network_list(host_uri: str = None) -> list:
    host = host_uri or settings.default_host_uri
    conn = libvirt_driver.connect(host)
    try:
        return libvirt_driver.network_list(conn)
    finally:
        if conn is not None:
            libvirt_driver.close(conn)


def network_delete(name: str, host_uri: str = None) -> dict:
    host = host_uri or settings.default_host_uri
    conn = libvirt_driver.connect(host)
    try:
        libvirt_driver.network_delete(conn, name)
        return {"name": name}
    finally:
        if conn is not None:
            libvirt_driver.close(conn)


def list_vms(host_uri: str = None) -> list:
    host = host_uri or settings.default_host_uri
    conn = libvirt_driver.connect(host)
    try:
        try:
            domains = conn.listAllDomains()
        except Exception:
            names = (
                conn.listDefinedDomains() if hasattr(conn, "listDefinedDomains") else []
            )
            return [{"name": n, "state": "unknown", "ip_address": None} for n in names]

        result = []
        for d in domains:
            try:
                name = d.name()
            except Exception:
                name = "unknown"
            try:
                active = d.isActive()
                state = "running" if active == 1 else "stopped"
            except Exception:
                state = "unknown"
            ip = network.get_vm_ip(conn, name) if state == "running" else None
            result.append({"name": name, "state": state, "ip_address": ip})
        return result
    finally:
        if conn is not None:
            libvirt_driver.close(conn)


def attach_iso(req: VMISORequest) -> None:
    host = req.host_uri or settings.default_host_uri
    conn = libvirt_driver.connect(host)
    try:
        libvirt_driver.attach_iso(conn, req.name, req.iso_path)
        logger.info("ISO '%s' attached to VM '%s'", req.iso_path, req.name)
    finally:
        if conn is not None:
            libvirt_driver.close(conn)


def _vnc_host() -> str:
    """Return the host IP reachable from inside container.
    VNC listens on 0.0.0.0; use the default gateway (host) when in Docker,
    fall back to loopback when running natively.
    """
    try:
        with open("/proc/net/route") as f:
            for line in f:
                fields = line.strip().split()
                if fields[1] == "00000000" and fields[2] != "00000000":
                    gw = fields[2]
                    ip = ".".join(str(int(gw[i:i+2], 16)) for i in [6,4,2,0])
                    return ip
    except Exception:
        pass
    return "127.0.0.1"


def get_vnc_info(name: str, host_uri: str = None) -> Optional[dict]:
    host = host_uri or settings.default_host_uri
    conn = libvirt_driver.connect(host)
    try:
        try:
            dom = conn.lookupByName(name)
        except Exception:
            return None
        if dom.isActive() != 1:
            return {"name": name, "state": "stopped", "vnc_port": None}
        vnc_port = libvirt_driver.get_vnc_port(conn, name)
        return {
            "name": name,
            "state": "running",
            "vnc_port": vnc_port,
            "vnc_host": _vnc_host(),
            "ws_url": f"/vm/vnc/ws/{name}",
        }
    finally:
        if conn is not None:
            libvirt_driver.close(conn)


def detach_iso(name: str, host_uri: str = None) -> None:
    host = host_uri or settings.default_host_uri
    conn = libvirt_driver.connect(host)
    try:
        libvirt_driver.detach_iso(conn, name)
        logger.info("CDROM detached from VM '%s'", name)
    finally:
        if conn is not None:
            libvirt_driver.close(conn)


def _render_domain_xml(spec: VMSpec) -> str:
    escaped_name = html.escape(spec.name, quote=True)
    memory = spec.memory_mb
    vcpu = spec.cpu
    disk_path = html.escape(spec.disk_path or "", quote=True)
    net_name = html.escape(spec.network or "default", quote=True)

    devices = f"""
    <disk type='file' device='disk'>
      <driver name='qemu' type='qcow2'/>
      <source file='{disk_path}'/>
      <target dev='vda' bus='virtio'/>
    </disk>"""

    if spec.iso_path:
        iso = html.escape(spec.iso_path, quote=True)
        devices += f"""
    <disk type='file' device='cdrom'>
      <driver name='qemu' type='raw'/>
      <source file='{iso}'/>
      <target dev='sda' bus='sata'/>
      <readonly/>
      <boot order='1'/>
    </disk>"""

    if spec.cloud_init_iso:
        ci = html.escape(spec.cloud_init_iso, quote=True)
        devices += f"""
    <disk type='file' device='cdrom'>
      <driver name='qemu' type='raw'/>
      <source file='{ci}'/>
      <target dev='sdb' bus='sata'/>
      <readonly/>
    </disk>"""

    devices += f"""
    <interface type='network'>
      <source network='{net_name}'/>
      <model type='virtio'/>
    </interface>
    <graphics type='vnc' port='-1' autoport='yes' listen='0.0.0.0'>
      <listen type='address' address='0.0.0.0'/>
    </graphics>
    <video>
      <model type='virtio' heads='1' primary='yes'/>
    </video>
    <serial type='pty'>
      <target port='0'/>
    </serial>
    <console type='pty'>
      <target type='serial' port='0'/>
    </console>"""

    os_section = """<os>
    <type arch='x86_64'>hvm</type>"""

    if spec.iso_path:
        os_section += "\n    <boot dev='cdrom'/>"
    os_section += "\n  </os>"

    max_memory = max(memory * 2, 65536)  # allow double or 64GB max for hotplug
    max_vcpus = max(vcpu * 4, 32)  # allow 4x or 32 max for hotplug
    xml = f"""<domain type='kvm'>
  <name>{escaped_name}</name>
  <memory unit='MiB'>{memory}</memory>
  <maxMemory unit='MiB'>{max_memory}</maxMemory>
  <vcpu placement='static' current='{vcpu}'>{max_vcpus}</vcpu>
  {os_section}
  <features>
    <acpi/>
    <apic/>
  </features>
  <clock offset='utc'/>
  <on_poweroff>destroy</on_poweroff>
  <on_reboot>restart</on_reboot>
  <on_crash>restart</on_crash>
  <devices>
    <emulator>/usr/bin/qemu-system-x86_64</emulator>{devices}
  </devices>
</domain>"""
    return xml
