from app.api.schemas import VMCreateRequest, VMActionRequest
from app.infrastructure import libvirt_driver, storage, network
from app.errors import ServiceError, InfrastructureError
from app.models.vm_spec import VMSpec
from app.config import settings
import logging

logger = logging.getLogger(__name__)


def create_vm(req: VMCreateRequest) -> dict:
    host = req.host_uri or settings.default_host_uri
    spec = VMSpec(
        name=req.name,
        cpu=req.cpu,
        memory_mb=req.memory_mb,
        disk_gb=req.disk_gb,
        image=req.image,
        network_bridge=req.network_bridge,
    )

    # storage: create qcow2 based on image
    try:
        disk_path = storage.prepare_disk(spec.image, spec.name, spec.disk_gb)
    except FileNotFoundError as e:
        raise ServiceError(str(e), code="IMAGE_NOT_FOUND", http_status=400)
    except Exception as e:
        raise ServiceError(f"storage error: {e}", code="STORAGE_ERROR", http_status=500)
    spec.disk_path = disk_path

    # render minimal domain XML
    xml = _render_domain_xml(spec)

    try:
        conn = libvirt_driver.connect(host)
    except InfrastructureError:
        raise

    try:
        domain = libvirt_driver.define_vm(conn, xml)
        libvirt_driver.start_vm(conn, domain)
        return {"name": spec.name, "domain": domain}
    except InfrastructureError:
        raise
    finally:
        libvirt_driver.close(conn)


def start_vm(req: VMActionRequest) -> None:
    host = req.host_uri or settings.default_host_uri
    conn = libvirt_driver.connect(host)
    try:
        libvirt_driver.start_vm(conn, req.name)
    finally:
        libvirt_driver.close(conn)


def stop_vm(req: VMActionRequest) -> None:
    host = req.host_uri or settings.default_host_uri
    conn = libvirt_driver.connect(host)
    try:
        libvirt_driver.stop_vm(conn, req.name)
    finally:
        libvirt_driver.close(conn)


def delete_vm(req: VMActionRequest) -> None:
    host = req.host_uri or settings.default_host_uri
    conn = libvirt_driver.connect(host)
    try:
        libvirt_driver.stop_vm(conn, req.name)
    except Exception:
        logger.exception("Error stopping VM before undefine (may be already stopped)")
    try:
        libvirt_driver.undefine_vm(conn, req.name, remove_storage=True)
    finally:
        libvirt_driver.close(conn)


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
        libvirt_driver.close(conn)


def get_vm_info(name: str, host_uri: str = None) -> dict | None:
    host = host_uri or settings.default_host_uri
    conn = libvirt_driver.connect(host)
    try:
        try:
            dom = conn.lookupByName(name)
        except Exception:
            return None
        active = dom.isActive()
        return {"name": name, "state": "running" if active == 1 else "stopped"}
    finally:
        libvirt_driver.close(conn)


def list_vms(host_uri: str = None) -> list:
    host = host_uri or settings.default_host_uri
    conn = libvirt_driver.connect(host)
    try:
        # prefer listAllDomains for richer info; tests may mock this
        try:
            domains = conn.listAllDomains()
        except Exception:
            # fallback to defined domains if listAllDomains not available
            names = (
                conn.listDefinedDomains() if hasattr(conn, "listDefinedDomains") else []
            )
            return [{"name": n, "state": "unknown"} for n in names]

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
            result.append({"name": name, "state": state})
        return result
    finally:
        libvirt_driver.close(conn)


def _render_domain_xml(spec: VMSpec) -> str:
    # minimal libvirt domain XML for qemu
    xml = f"""
<domain type='kvm'>
  <name>{spec.name}</name>
  <memory unit='MiB'>{spec.memory_mb}</memory>
  <vcpu>{spec.cpu}</vcpu>
  <os>
    <type arch='x86_64'>hvm</type>
  </os>
  <devices>
    <emulator>/usr/bin/qemu-system-x86_64</emulator>
    <disk type='file' device='disk'>
      <driver name='qemu' type='qcow2'/>
      <source file='{spec.disk_path}'/>
      <target dev='vda' bus='virtio'/>
    </disk>
    <interface type='bridge'>
      <source bridge='{spec.network_bridge}'/>
      <model type='virtio'/>
    </interface>
    <graphics type='vnc' port='-1'/>
  </devices>
</domain>
"""
    return xml
