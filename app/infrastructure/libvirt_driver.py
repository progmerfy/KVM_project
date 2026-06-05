import logging
from typing import Optional
from app.errors import InfrastructureError

logger = logging.getLogger(__name__)

try:
    import libvirt
except ImportError:
    libvirt = None  # type: ignore[assignment]
    logger.warning(
        "libvirt-python is not installed. "
        "Install it via your system package manager. "
        "All libvirt operations will fail at runtime."
    )

LibvirtError = InfrastructureError


def _check_libvirt():
    if libvirt is None:
        raise LibvirtError(
            "libvirt-python is not installed. "
            "Install it via your system package manager"
        )


def connect(uri: Optional[str] = None):
    _check_libvirt()
    if uri is None:
        raise LibvirtError("host URI is required")
    try:
        conn = libvirt.open(uri)
    except Exception as e:
        raise LibvirtError(str(e))
    if conn is None:
        raise LibvirtError(f"failed to open connection to {uri}")
    return conn


def define_vm(conn, xml: str) -> str:
    _check_libvirt()
    try:
        dom = conn.defineXML(xml)
        if dom is None:
            raise LibvirtError("defineXML returned None")
        return dom.name()
    except libvirt.libvirtError as e:
        raise LibvirtError(str(e))


def start_vm(conn, domain_name: str) -> None:
    _check_libvirt()
    try:
        dom = conn.lookupByName(domain_name)
        if dom.isActive() == 1:
            return
        dom.create()
    except libvirt.libvirtError as e:
        raise LibvirtError(str(e))


def stop_vm(conn, domain_name: str, timeout: int = 30) -> None:
    _check_libvirt()
    try:
        dom = conn.lookupByName(domain_name)
        if dom.isActive() == 0:
            return
        dom.shutdown()
    except libvirt.libvirtError as e:
        raise LibvirtError(str(e))


def destroy_vm(conn, domain_name: str) -> None:
    _check_libvirt()
    try:
        dom = conn.lookupByName(domain_name)
        if dom.isActive() == 0:
            return
        dom.destroy()
    except libvirt.libvirtError as e:
        raise LibvirtError(str(e))


def reboot_vm(conn, domain_name: str) -> None:
    _check_libvirt()
    try:
        dom = conn.lookupByName(domain_name)
        if dom.isActive() == 0:
            raise LibvirtError(f"VM '{domain_name}' is not running")
        dom.reboot(0)
    except libvirt.libvirtError as e:
        raise LibvirtError(str(e))


def reset_vm(conn, domain_name: str) -> None:
    _check_libvirt()
    try:
        dom = conn.lookupByName(domain_name)
        if dom.isActive() == 0:
            raise LibvirtError(f"VM '{domain_name}' is not running")
        dom.reset()
    except libvirt.libvirtError as e:
        raise LibvirtError(str(e))


def undefine_vm(conn, domain_name: str, remove_storage: bool = True) -> None:
    _check_libvirt()
    try:
        dom = conn.lookupByName(domain_name)
        if dom.isActive() == 1:
            dom.destroy()
        if remove_storage:
            disks = _get_disk_paths(dom)
            dom.undefine()
            for disk in disks:
                try:
                    _remove_storage(disk)
                except Exception as e:
                    logger.warning("Failed to remove disk %s: %s", disk, e)
        else:
            dom.undefineFlags(0)
    except libvirt.libvirtError as e:
        raise LibvirtError(str(e))


def attach_iso(conn, domain_name: str, iso_path: str) -> None:
    _check_libvirt()
    try:
        dom = conn.lookupByName(domain_name)
        xml = f"""<disk type='file' device='cdrom'>
  <driver name='qemu' type='raw'/>
  <source file='{iso_path}'/>
  <target dev='sda' bus='sata'/>
  <readonly/>
</disk>"""
        dom.attachDevice(xml)
        logger.info("ISO %s attached to %s", iso_path, domain_name)
    except libvirt.libvirtError as e:
        raise LibvirtError(f"failed to attach ISO: {e}")


def detach_iso(conn, domain_name: str, target_dev: str = "sda") -> None:
    _check_libvirt()
    try:
        dom = conn.lookupByName(domain_name)
        xml = f"""<disk type='file' device='cdrom'>
  <driver name='qemu' type='raw'/>
  <target dev='{target_dev}' bus='sata'/>
  <readonly/>
</disk>"""
        dom.detachDevice(xml)
        logger.info("CDROM %s detached from %s", target_dev, domain_name)
    except libvirt.libvirtError as e:
        raise LibvirtError(f"failed to detach ISO: {e}")


def get_domain_xml(conn, domain_name: str, flags: int = 0) -> Optional[str]:
    _check_libvirt()
    try:
        dom = conn.lookupByName(domain_name)
        return dom.XMLDesc(flags)
    except libvirt.libvirtError as e:
        raise LibvirtError(str(e))


def get_vnc_port(conn, domain_name: str) -> Optional[int]:
    _check_libvirt()
    try:
        dom = conn.lookupByName(domain_name)
        if dom.isActive() != 1:
            return None
        xml_desc = dom.XMLDesc(0)
        import re

        match = re.search(r"<graphics type='vnc' port='(\d+)'", xml_desc)
        if match:
            port = int(match.group(1))
            if port > 0:
                return port
        return None
    except libvirt.libvirtError as e:
        raise LibvirtError(str(e))


def _get_disk_paths(dom) -> list[str]:
    paths = []
    try:
        xml_desc = dom.XMLDesc(0)
        import re

        for match in re.finditer(r"<source file='([^']+)'", xml_desc):
            paths.append(match.group(1))
    except Exception as e:
        logger.warning("Failed to parse domain XML for disk paths: %s", e)
    return paths


def _remove_storage(path: str) -> None:
    import os

    if os.path.exists(path):
        os.remove(path)
        logger.info("Removed disk: %s", path)


def close(conn) -> None:
    try:
        conn.close()
    except Exception:
        pass
