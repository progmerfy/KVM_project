"""Lightweight stub for libvirt to allow running unit-tests without system libvirt."""


class libvirtError(Exception):
    pass


def open(uri):
    raise libvirtError("stub libvirt: no backend available")
