import pytest
from unittest.mock import MagicMock, patch

import app.infrastructure.libvirt_driver as driver


def test_connect_failure():
    with patch("app.infrastructure.libvirt_driver.libvirt.open", return_value=None):
        with pytest.raises(driver.LibvirtError):
            driver.connect("qemu:///system")


def test_define_vm_success():
    mock_conn = MagicMock()
    mock_dom = MagicMock()
    mock_dom.name.return_value = "vm1"
    mock_conn.defineXML.return_value = mock_dom

    with patch(
        "app.infrastructure.libvirt_driver.libvirt.open", return_value=mock_conn
    ):
        conn = driver.connect("qemu:///system")
        name = driver.define_vm(conn, "<xml/>")
        assert name == "vm1"


def test_start_vm_active_and_inactive():
    mock_conn = MagicMock()
    dom_active = MagicMock()
    dom_active.isActive.return_value = 1
    dom_inactive = MagicMock()
    dom_inactive.isActive.return_value = 0

    mock_conn.lookupByName.side_effect = [dom_active, dom_inactive]

    with patch(
        "app.infrastructure.libvirt_driver.libvirt.open", return_value=mock_conn
    ):
        conn = driver.connect("qemu:///system")
        # active: should be no exception and no create call
        driver.start_vm(conn, "vm_active")
        assert not dom_active.create.called

        # inactive: create should be called
        driver.start_vm(conn, "vm_inactive")
        assert dom_inactive.create.called


def test_stop_vm_active_and_inactive():
    mock_conn = MagicMock()
    dom_inactive = MagicMock()
    dom_inactive.isActive.return_value = 0
    dom_active = MagicMock()
    dom_active.isActive.return_value = 1

    mock_conn.lookupByName.side_effect = [dom_inactive, dom_active]

    with patch(
        "app.infrastructure.libvirt_driver.libvirt.open", return_value=mock_conn
    ):
        conn = driver.connect("qemu:///system")
        # inactive: nothing to shutdown
        driver.stop_vm(conn, "vm_inactive")
        assert not dom_inactive.shutdown.called

        # active: shutdown should be called
        driver.stop_vm(conn, "vm_active")
        assert dom_active.shutdown.called


def test_undefine_vm_destroy_and_undefine():
    mock_conn = MagicMock()
    dom_active = MagicMock()
    dom_active.isActive.return_value = 1
    dom_inactive = MagicMock()
    dom_inactive.isActive.return_value = 0

    mock_conn.lookupByName.side_effect = [dom_active, dom_inactive]

    with patch(
        "app.infrastructure.libvirt_driver.libvirt.open", return_value=mock_conn
    ):
        conn = driver.connect("qemu:///system")
        driver.undefine_vm(conn, "vm_active")
        assert dom_active.destroy.called
        assert dom_active.undefineFlags.called

        driver.undefine_vm(conn, "vm_inactive")
        assert dom_inactive.undefineFlags.called
