import logging
import html
import secrets
import string
from typing import Optional

from app.api.schemas import VMCreateRequest, VMActionRequest, VMISORequest
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
            m = re.search(r"<vcpu(?: placement='static')?>(\d+)</vcpu>", xml)
            if m:
                info["cpu"] = int(m.group(1))
        return info
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

    xml = f"""<domain type='kvm'>
  <name>{escaped_name}</name>
  <memory unit='MiB'>{memory}</memory>
  <vcpu>{vcpu}</vcpu>
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
