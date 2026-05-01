import libvirt
from typing import Optional
from app.errors import InfrastructureError

# Maintain LibvirtError name for tests/backwards compatibility
LibvirtError = InfrastructureError


def connect(uri: Optional[str] = None):
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
    try:
        dom = conn.defineXML(xml)
        if dom is None:
            raise LibvirtError("defineXML returned None")
        return dom.name()
    except libvirt.libvirtError as e:
        raise LibvirtError(str(e))


def start_vm(conn, domain_name: str) -> None:
    try:
        dom = conn.lookupByName(domain_name)
        if dom.isActive() == 1:
            return
        dom.create()
    except libvirt.libvirtError as e:
        raise LibvirtError(str(e))


def stop_vm(conn, domain_name: str, timeout: int = 30) -> None:
    try:
        dom = conn.lookupByName(domain_name)
        if dom.isActive() == 0:
            return
        dom.shutdown()
    except libvirt.libvirtError as e:
        raise LibvirtError(str(e))


def undefine_vm(conn, domain_name: str, remove_storage: bool = True) -> None:
    try:
        dom = conn.lookupByName(domain_name)
        if dom.isActive() == 1:
            dom.destroy()
        dom.undefineFlags(0)
        # storage removal is left to storage helper in real systems
    except libvirt.libvirtError as e:
        raise LibvirtError(str(e))


def close(conn) -> None:
    try:
        conn.close()
    except Exception:
        pass
