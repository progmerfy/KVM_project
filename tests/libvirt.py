"""Lightweight stub for libvirt to allow running unit-tests without system libvirt."""


class libvirtError(Exception):
    pass


VIR_DOMAIN_UNDEFINE_SNAPSHOTS_METADATA = 1
VIR_DOMAIN_XML_INACTIVE = 2
VIR_IP_ADDR_TYPE_IPV4 = 0
VIR_IP_ADDR_TYPE_IPV6 = 1
VIR_DOMAIN_INTERFACE_ADDRESSES_SOURCE_AGENT = 1


def open(uri):
    raise libvirtError("stub libvirt: no backend available")
