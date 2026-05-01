"""Lightweight stub for libvirt to allow running unit-tests without system libvirt.
This file is used only for testing/development when libvirt-python is not installed.
"""


class libvirtError(Exception):
    pass


def open(uri):
    raise libvirtError("stub libvirt: no backend available")
