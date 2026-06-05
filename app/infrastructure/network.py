import logging
import random
from typing import Optional

from app.errors import InfrastructureError

logger = logging.getLogger(__name__)


def generate_mac() -> str:
    mac = [
        0x52, 0x54, 0x00,
        random.randrange(0x00, 0xFF),
        random.randrange(0x00, 0xFF),
        random.randrange(0x00, 0xFF),
    ]
    return ":".join("%02x" % x for x in mac)


def ensure_default_network(conn) -> dict:
    """Ensure the default NAT network exists and is active.
    Creates it if missing. Returns network info dict.
    """
    try:
        network = conn.networkLookupByName("default")
    except Exception:
        logger.info("Default network not found, creating it...")
        xml = """<network>
  <name>default</name>
  <forward mode='nat'>
    <nat>
      <port start='1024' end='65535'/>
    </nat>
  </forward>
  <bridge name='virbr0' stp='on' delay='0'/>
  <ip address='192.168.122.1' netmask='255.255.255.0'>
    <dhcp>
      <range start='192.168.122.2' end='192.168.122.254'/>
    </dhcp>
  </ip>
</network>"""
        network = conn.networkDefineXML(xml)
        if network is None:
            raise InfrastructureError("failed to define default network")

    active = network.isActive()
    if not active:
        network.create()
        logger.info("Default network activated")

    bridge = network.bridgeName()
    return {"name": "default", "bridge": bridge, "active": True}


def get_vm_ip(conn, domain_name: str) -> Optional[str]:
    """Get the IP address of a running VM by querying DHCP leases."""
    try:
        dom = conn.lookupByName(domain_name)
    except Exception:
        return None

    if dom.isActive() != 1:
        return None

    try:
        macs = _get_domain_macs(dom)
    except Exception:
        return None

    networks = _list_networks(conn)
    for mac in macs:
        for net_name in networks:
            try:
                network = conn.networkLookupByName(net_name)
                leases = network.DHCPLeases(mac)
                for lease in leases:
                    if lease.get("ipaddr"):
                        return lease["ipaddr"]
            except Exception:
                continue

    return None


def _get_domain_macs(dom) -> list[str]:
    """Extract MAC addresses from domain XML."""
    macs = []
    try:
        xml_desc = dom.XMLDesc(0)
        import re
        for match in re.finditer(r"mac address='([^']+)'", xml_desc):
            macs.append(match.group(1))
    except Exception as e:
        logger.warning("Failed to parse MACs from domain XML: %s", e)
    return macs


def _list_networks(conn) -> list[str]:
    """List all libvirt network names on the connection."""
    try:
        return conn.listNetworks() + conn.listDefinedNetworks()
    except Exception:
        return []
