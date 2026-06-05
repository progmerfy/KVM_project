import pytest
from unittest.mock import MagicMock, patch

import app.infrastructure.libvirt_driver as driver


@pytest.fixture
def fake_libvirt():
    fake = MagicMock()
    fake.libvirtError = Exception
    with patch("app.infrastructure.libvirt_driver.libvirt", fake), \
         patch("app.infrastructure.libvirt_driver._check_libvirt"):
        yield fake


def test_connect_failure(fake_libvirt):
    fake_libvirt.open.return_value = None
    with pytest.raises(driver.LibvirtError):
        driver.connect("qemu:///system")


def test_define_vm_success(fake_libvirt):
    mock_conn = MagicMock()
    mock_dom = MagicMock()
    mock_dom.name.return_value = "vm1"
    mock_conn.defineXML.return_value = mock_dom

    fake_libvirt.open.return_value = mock_conn
    conn = driver.connect("qemu:///system")
    name = driver.define_vm(conn, "<xml/>")
    assert name == "vm1"


def test_start_vm_active_and_inactive(fake_libvirt):
    mock_conn = MagicMock()
    dom_active = MagicMock()
    dom_active.isActive.return_value = 1
    dom_inactive = MagicMock()
    dom_inactive.isActive.return_value = 0

    mock_conn.lookupByName.side_effect = [dom_active, dom_inactive]
    fake_libvirt.open.return_value = mock_conn

    conn = driver.connect("qemu:///system")
    driver.start_vm(conn, "vm_active")
    assert not dom_active.create.called

    driver.start_vm(conn, "vm_inactive")
    assert dom_inactive.create.called


def test_stop_vm_active_and_inactive(fake_libvirt):
    mock_conn = MagicMock()
    dom_inactive = MagicMock()
    dom_inactive.isActive.return_value = 0
    dom_active = MagicMock()
    dom_active.isActive.return_value = 1

    mock_conn.lookupByName.side_effect = [dom_inactive, dom_active]
    fake_libvirt.open.return_value = mock_conn

    conn = driver.connect("qemu:///system")
    driver.stop_vm(conn, "vm_inactive")
    assert not dom_inactive.shutdown.called

    driver.stop_vm(conn, "vm_active")
    assert dom_active.shutdown.called


def test_reboot_vm(fake_libvirt):
    mock_conn = MagicMock()
    dom = MagicMock()
    dom.isActive.return_value = 1
    mock_conn.lookupByName.return_value = dom
    fake_libvirt.open.return_value = mock_conn

    conn = driver.connect("qemu:///system")
    driver.reboot_vm(conn, "vm1")
    assert dom.reboot.called


def test_reboot_vm_not_running(fake_libvirt):
    mock_conn = MagicMock()
    dom = MagicMock()
    dom.isActive.return_value = 0
    mock_conn.lookupByName.return_value = dom
    fake_libvirt.open.return_value = mock_conn

    conn = driver.connect("qemu:///system")
    with pytest.raises(driver.LibvirtError):
        driver.reboot_vm(conn, "vm1")


def test_reset_vm(fake_libvirt):
    mock_conn = MagicMock()
    dom = MagicMock()
    dom.isActive.return_value = 1
    mock_conn.lookupByName.return_value = dom
    fake_libvirt.open.return_value = mock_conn

    conn = driver.connect("qemu:///system")
    driver.reset_vm(conn, "vm1")
    assert dom.reset.called


def test_undefine_vm_destroy_and_undefine(fake_libvirt):
    mock_conn = MagicMock()
    dom_active = MagicMock()
    dom_active.isActive.return_value = 1
    dom_active.XMLDesc.return_value = (
        "<domain><devices><disk type='file'>"
        "<source file='/tmp/test.qcow2'/></disk></devices></domain>"
    )
    dom_inactive = MagicMock()
    dom_inactive.isActive.return_value = 0
    dom_inactive.XMLDesc.return_value = "<domain/>"

    mock_conn.lookupByName.side_effect = [dom_active, dom_inactive]
    fake_libvirt.open.return_value = mock_conn

    with patch("app.infrastructure.libvirt_driver._remove_storage"):
        conn = driver.connect("qemu:///system")
        driver.undefine_vm(conn, "vm_active")
        assert dom_active.destroy.called
        assert dom_active.undefine.called

        driver.undefine_vm(conn, "vm_inactive")
        assert dom_inactive.undefine.called


def test_destroy_vm(fake_libvirt):
    mock_conn = MagicMock()
    dom_active = MagicMock()
    dom_active.isActive.return_value = 1
    dom_inactive = MagicMock()
    dom_inactive.isActive.return_value = 0

    mock_conn.lookupByName.side_effect = [dom_active, dom_inactive]
    fake_libvirt.open.return_value = mock_conn

    conn = driver.connect("qemu:///system")
    driver.destroy_vm(conn, "vm_active")
    assert dom_active.destroy.called

    driver.destroy_vm(conn, "vm_inactive")
    assert not dom_inactive.destroy.called


def test_attach_iso(fake_libvirt):
    mock_conn = MagicMock()
    dom = MagicMock()
    mock_conn.lookupByName.return_value = dom
    fake_libvirt.open.return_value = mock_conn

    conn = driver.connect("qemu:///system")
    driver.attach_iso(conn, "vm1", "/path/to/os.iso")

    dom.attachDevice.assert_called_once()
    call_arg = dom.attachDevice.call_args[0][0]
    assert "device='cdrom'" in call_arg
    assert "/path/to/os.iso" in call_arg


def test_detach_iso(fake_libvirt):
    mock_conn = MagicMock()
    dom = MagicMock()
    mock_conn.lookupByName.return_value = dom
    fake_libvirt.open.return_value = mock_conn

    conn = driver.connect("qemu:///system")
    driver.detach_iso(conn, "vm1")

    dom.detachDevice.assert_called_once()


def test_get_domain_xml(fake_libvirt):
    mock_conn = MagicMock()
    dom = MagicMock()
    dom.XMLDesc.return_value = "<domain><name>vm1</name></domain>"
    mock_conn.lookupByName.return_value = dom
    fake_libvirt.open.return_value = mock_conn

    conn = driver.connect("qemu:///system")
    xml = driver.get_domain_xml(conn, "vm1")
    assert "<domain>" in xml


def test_get_vnc_port_running(fake_libvirt):
    mock_conn = MagicMock()
    dom = MagicMock()
    dom.isActive.return_value = 1
    dom.XMLDesc.return_value = (
        "<domain><devices><graphics type='vnc' port='5901' autoport='yes'"
        " listen='127.0.0.1'/></devices></domain>"
    )
    mock_conn.lookupByName.return_value = dom
    fake_libvirt.open.return_value = mock_conn

    conn = driver.connect("qemu:///system")
    port = driver.get_vnc_port(conn, "vm1")
    assert port == 5901


def test_get_vnc_port_stopped(fake_libvirt):
    mock_conn = MagicMock()
    dom = MagicMock()
    dom.isActive.return_value = 0
    mock_conn.lookupByName.return_value = dom
    fake_libvirt.open.return_value = mock_conn

    conn = driver.connect("qemu:///system")
    port = driver.get_vnc_port(conn, "vm1")
    assert port is None
