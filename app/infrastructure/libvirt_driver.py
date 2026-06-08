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


def attach_disk(conn, domain_name: str, source_path: str, target_dev: str = "vdb", bus: str = "virtio") -> None:
    _check_libvirt()
    try:
        xml = f"""<disk type='file' device='disk'>
  <driver name='qemu' type='qcow2'/>
  <source file='{source_path}'/>
  <target dev='{target_dev}' bus='{bus}'/>
</disk>"""
        dom = conn.lookupByName(domain_name)
        dom.attachDevice(xml)
        logger.info("Disk %s attached to '%s' as %s", source_path, domain_name, target_dev)
    except libvirt.libvirtError as e:
        raise LibvirtError(f"failed to attach disk: {e}")


def detach_disk(conn, domain_name: str, target_dev: str) -> None:
    _check_libvirt()
    try:
        xml = f"""<disk type='file' device='disk'>
  <driver name='qemu' type='qcow2'/>
  <target dev='{target_dev}' bus='virtio'/>
</disk>"""
        dom = conn.lookupByName(domain_name)
        dom.detachDevice(xml)
        logger.info("Disk %s detached from '%s'", target_dev, domain_name)
    except libvirt.libvirtError as e:
        raise LibvirtError(f"failed to detach disk: {e}")


def create_disk(path: str, size_gb: int) -> None:
    import subprocess
    try:
        subprocess.check_call(
            ["qemu-img", "create", "-f", "qcow2", path, f"{size_gb}G"],
            stdout=subprocess.DEVNULL,
        )
        logger.info("Created disk: %s (%dG)", path, size_gb)
    except subprocess.CalledProcessError as e:
        raise LibvirtError(f"failed to create disk: {e}")


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


def snapshot_create(conn, domain_name: str, snap_name: str) -> None:
    _check_libvirt()
    try:
        dom = conn.lookupByName(domain_name)
        xml = f"""<domainsnapshot>
  <name>{snap_name}</name>
  <description>Snapshot created by KVM Manager API</description>
</domainsnapshot>"""
        dom.snapshotCreateXML(xml)
        logger.info("Snapshot '%s' created for '%s'", snap_name, domain_name)
    except libvirt.libvirtError as e:
        raise LibvirtError(f"failed to create snapshot: {e}")


def snapshot_list(conn, domain_name: str) -> list[dict]:
    _check_libvirt()
    try:
        dom = conn.lookupByName(domain_name)
        snaps = dom.listAllSnapshots()
        return [
            {
                "name": s.getName(),
                "created": s.getXMLDesc(0),
            }
            for s in snaps
        ]
    except libvirt.libvirtError as e:
        raise LibvirtError(f"failed to list snapshots: {e}")


def snapshot_revert(conn, domain_name: str, snap_name: str) -> None:
    _check_libvirt()
    try:
        dom = conn.lookupByName(domain_name)
        snap = dom.snapshotLookupByName(snap_name)
        dom.revertToSnapshot(snap)
        logger.info("Reverted '%s' to snapshot '%s'", domain_name, snap_name)
    except libvirt.libvirtError as e:
        raise LibvirtError(f"failed to revert snapshot: {e}")


def snapshot_delete(conn, domain_name: str, snap_name: str) -> None:
    _check_libvirt()
    try:
        dom = conn.lookupByName(domain_name)
        snap = dom.snapshotLookupByName(snap_name)
        snap.delete()
        logger.info("Deleted snapshot '%s' for '%s'", snap_name, domain_name)
    except libvirt.libvirtError as e:
        raise LibvirtError(f"failed to delete snapshot: {e}")


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
        for match in re.finditer(
            r"<disk type='file' device='disk'>.*?<source file='([^']+)'",
            xml_desc, re.DOTALL,
        ):
            paths.append(match.group(1))
    except Exception as e:
        logger.warning("Failed to parse domain XML for disk paths: %s", e)
    return paths


def _remove_storage(path: str) -> None:
    import os

    if os.path.exists(path):
        os.remove(path)
        logger.info("Removed disk: %s", path)


def redefine_domain(conn, domain_name: str, new_xml: str) -> None:
    _check_libvirt()
    try:
        dom = conn.lookupByName(domain_name)
        dom.undefine()
        conn.defineXML(new_xml)
        logger.info("Redefined domain '%s'", domain_name)
    except libvirt.libvirtError as e:
        raise LibvirtError(f"failed to redefine domain: {e}")


def get_domain_xml(conn, domain_name: str, flags: int = 0) -> Optional[str]:
    _check_libvirt()
    try:
        dom = conn.lookupByName(domain_name)
        return dom.XMLDesc(flags)
    except libvirt.libvirtError as e:
        raise LibvirtError(str(e))


def set_vcpus(conn, domain_name: str, count: int) -> None:
    _check_libvirt()
    try:
        dom = conn.lookupByName(domain_name)
        if dom.isActive() == 1:
            dom.setVcpus(count)
        else:
            xml = dom.XMLDesc(libvirt.VIR_DOMAIN_XML_INACTIVE)
            import re
            xml = re.sub(
                r"<vcpu[^>]*>.*?</vcpu>",
                f"<vcpu placement='static'>{count}</vcpu>",
                xml,
            )
            redefine_domain(conn, domain_name, xml)
        logger.info("Set vCPUs for '%s' to %d", domain_name, count)
    except libvirt.libvirtError as e:
        raise LibvirtError(f"failed to set vCPUs: {e}")


def set_memory(conn, domain_name: str, memory_kib: int) -> None:
    _check_libvirt()
    try:
        dom = conn.lookupByName(domain_name)
        if dom.isActive() == 1:
            dom.setMemory(memory_kib)
        else:
            xml = dom.XMLDesc(libvirt.VIR_DOMAIN_XML_INACTIVE)
            import re
            xml = re.sub(
                r"<memory[^>]*>.*?</memory>",
                f"<memory unit='KiB'>{memory_kib}</memory><currentMemory unit='KiB'>{memory_kib}</currentMemory>",
                xml,
            )
            redefine_domain(conn, domain_name, xml)
        logger.info("Set memory for '%s' to %d KiB", domain_name, memory_kib)
    except libvirt.libvirtError as e:
        raise LibvirtError(f"failed to set memory: {e}")


def block_resize(conn, domain_name: str, device: str, size_kib: int) -> None:
    _check_libvirt()
    try:
        dom = conn.lookupByName(domain_name)
        dom.blockResize(device, size_kib)
        logger.info("Resized block device %s to %d KiB for '%s'", device, size_kib, domain_name)
    except libvirt.libvirtError as e:
        raise LibvirtError(f"failed to resize block device: {e}")


def network_create_nat(conn, name: str, bridge: str, subnet: str) -> None:
    _check_libvirt()
    try:
        net_xml = f"""<network>
  <name>{name}</name>
  <forward mode='nat'/>
  <bridge name='{bridge}' stp='on' delay='0'/>
  <ip address='{subnet.rsplit("/", 1)[0]}' prefix='{subnet.rsplit("/", 1)[1]}'>
    <dhcp>
      <range start='{subnet.rsplit(".", 1)[0]}.2' end='{subnet.rsplit(".", 1)[0]}.254'/>
    </dhcp>
  </ip>
</network>"""
        conn.networkDefineXML(net_xml)
        net = conn.networkLookupByName(name)
        net.setAutostart(True)
        net.create()
        logger.info("NAT network '%s' created (%s, bridge %s)", name, subnet, bridge)
    except libvirt.libvirtError as e:
        raise LibvirtError(f"failed to create network: {e}")


def network_list(conn) -> list[dict]:
    _check_libvirt()
    try:
        nets = conn.listAllNetworks()
        result = []
        for net in nets:
            xml = net.XMLDesc(0)
            import re
            bridge_m = re.search(r"<bridge name='([^']+)'", xml)
            ip_m = re.search(r"<ip address='([^']+)'(?: prefix='(\d+)'| netmask='([^']+)')", xml)
            if ip_m:
                if ip_m.group(2):
                    prefix = ip_m.group(2)
                else:
                    nm = ip_m.group(3)
                    prefix = str(sum(bin(int(x)).count("1") for x in nm.split(".")))
                subnet = f"{ip_m.group(1)}/{prefix}"
            else:
                subnet = None
            result.append({
                "name": net.name(),
                "active": net.isActive() == 1,
                "autostart": net.autostart() == 1,
                "bridge": bridge_m.group(1) if bridge_m else None,
                "subnet": subnet,
            })
        return result
    except libvirt.libvirtError as e:
        raise LibvirtError(f"failed to list networks: {e}")


def network_delete(conn, name: str) -> None:
    _check_libvirt()
    try:
        net = conn.networkLookupByName(name)
        if net.isActive() == 1:
            net.destroy()
        net.undefine()
        logger.info("Network '%s' deleted", name)
    except libvirt.libvirtError as e:
        raise LibvirtError(f"failed to delete network: {e}")


def get_metrics(conn, domain_name: str) -> dict:
    _check_libvirt()
    try:
        dom = conn.lookupByName(domain_name)
        info = dom.info()
        state_map = {
            0: "stopped", 1: "running", 2: "blocked",
            3: "paused", 4: "shutdown", 5: "stopped", 6: "crashed",
        }
        cpu_time_ns = info[4]

        mem_stats = {}
        try:
            mem = dom.memoryStats()
            for key in ("available", "unused", "usable", "actual"):
                if key in mem:
                    mem_stats[key] = mem[key] // 1024
        except Exception:
            pass

        block_stats = {}
        try:
            xml = dom.XMLDesc(0)
            import re
            for m in re.finditer(r"<target dev='([^']+)'", xml):
                dev = m.group(1)
                try:
                    stats = dom.blockStats(dev)
                    block_stats[dev] = {
                        "rd_req": stats[0],
                        "rd_bytes": stats[1],
                        "wr_req": stats[2],
                        "wr_bytes": stats[3],
                    }
                except Exception:
                    pass
        except Exception:
            pass

        return {
            "state": state_map.get(info[0], "unknown"),
            "max_memory_mb": info[1] // 1024,
            "memory_mb": info[2] // 1024,
            "cpu_count": info[3],
            "cpu_time_ns": cpu_time_ns,
            "cpu_time_s": round(cpu_time_ns / 1e9, 3),
            "memory_stats": mem_stats,
            "block_stats": block_stats,
        }
    except libvirt.libvirtError as e:
        raise LibvirtError(f"failed to get metrics: {e}")


def rename_in_xml(xml: str, new_name: str) -> str:
    import re
    xml = re.sub(r"<name>[^<]+</name>", f"<name>{new_name}</name>", xml)
    xml = re.sub(
        r"<uuid>[^<]+</uuid>",
        lambda m: f"<uuid>{__import__('uuid').uuid4()}</uuid>",
        xml,
    )
    return xml


def copy_disk_image(src: str, dst: str) -> None:
    import subprocess, time
    for attempt in range(3):
        try:
            result = subprocess.run(
                ["qemu-img", "convert", "-f", "qcow2", "-O", "qcow2", "-U", src, dst],
                capture_output=True, text=True, timeout=120,
            )
            if result.returncode == 0:
                logger.info("Copied disk %s -> %s", src, dst)
                return
            logger.warning("qemu-img convert attempt %d failed: %s", attempt + 1, result.stderr.strip())
            time.sleep(2)
        except subprocess.TimeoutExpired:
            raise LibvirtError("disk copy timed out")
    raise LibvirtError(f"failed to copy disk image after 3 attempts")


def network_leases(conn) -> list[dict]:
    _check_libvirt()
    leases = []
    try:
        nets = conn.listAllNetworks()
        for net in nets:
            if not net.isActive():
                continue
            try:
                net_leases = net.DHCPLeases()
                for lease in net_leases:
                    leases.append({
                        "network": net.name(),
                        "ip": lease.get("ipaddr", ""),
                        "mac": lease.get("mac", ""),
                        "hostname": lease.get("hostname", "") or "",
                        "prefix": lease.get("prefix", 24),
                        "expirytime": lease.get("expirytime", 0),
                        "type": lease.get("type", 0),
                    })
            except Exception:
                continue
        return leases
    except libvirt.libvirtError as e:
        raise LibvirtError(f"failed to list network leases: {e}")


def close(conn) -> None:
    try:
        conn.close()
    except Exception:
        pass
