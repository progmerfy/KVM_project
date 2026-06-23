"""Unit tests for app.infrastructure.libvirt_driver — all libvirt operations with stubs."""

import os
import sys
import pytest
from unittest.mock import patch, MagicMock

# Ensure tests/ is importable for the libvirt stub
tests_dir = os.path.dirname(os.path.abspath(__file__))
if tests_dir not in sys.path:
    sys.path.insert(0, tests_dir)

from app.infrastructure.libvirt_driver import (
    connect, define_vm, start_vm, stop_vm, destroy_vm, reboot_vm, reset_vm,
    undefine_vm, attach_disk, detach_disk, create_disk, attach_iso, detach_iso,
    snapshot_create, snapshot_list, snapshot_revert, snapshot_delete,
    get_vnc_port, get_domain_xml, set_vcpus, set_memory, block_resize,
    network_create_nat, network_list, network_delete, get_metrics,
    rename_in_xml, copy_disk_image, network_leases, guest_agent_ip,
    close, _extract_creation_time,
)
from app.errors import InfrastructureError

import libvirt


class TestConnect:
    def test_connect_success(self):
        with patch.object(libvirt, "open", return_value=MagicMock()):
            conn = connect("qemu:///system")
            assert conn is not None

    def test_connect_no_uri(self):
        with pytest.raises(InfrastructureError, match="host URI is required"):
            connect()

    def test_connect_failure(self):
        with patch.object(libvirt, "open", side_effect=Exception("connection refused")):
            with pytest.raises(InfrastructureError):
                connect("qemu:///system")

    def test_connect_returns_none(self):
        with patch.object(libvirt, "open", return_value=None):
            with pytest.raises(InfrastructureError):
                connect("qemu:///system")


class TestDefineVM:
    def test_define_success(self):
        conn = MagicMock()
        dom = MagicMock()
        dom.name.return_value = "test-vm"
        conn.defineXML.return_value = dom
        name = define_vm(conn, "<domain><name>test-vm</name></domain>")
        assert name == "test-vm"

    def test_define_returns_none(self):
        conn = MagicMock()
        conn.defineXML.return_value = None
        with pytest.raises(InfrastructureError):
            define_vm(conn, "<domain/>")

    def test_define_libvirt_error(self):
        conn = MagicMock()
        conn.defineXML.side_effect = libvirt.libvirtError("bad xml")
        with pytest.raises(InfrastructureError):
            define_vm(conn, "<bad/>")


class TestVMLifecycle:
    def test_start_vm(self):
        conn = MagicMock()
        dom = MagicMock()
        dom.isActive.return_value = 0
        conn.lookupByName.return_value = dom
        start_vm(conn, "vm")
        dom.create.assert_called_once()

    def test_start_vm_already_running(self):
        conn = MagicMock()
        dom = MagicMock()
        dom.isActive.return_value = 1
        conn.lookupByName.return_value = dom
        start_vm(conn, "vm")
        dom.create.assert_not_called()

    def test_start_vm_not_found(self):
        conn = MagicMock()
        conn.lookupByName.side_effect = libvirt.libvirtError("not found")
        with pytest.raises(InfrastructureError):
            start_vm(conn, "ghost")

    def test_stop_vm(self):
        conn = MagicMock()
        dom = MagicMock()
        dom.isActive.return_value = 1
        conn.lookupByName.return_value = dom
        stop_vm(conn, "vm")
        dom.shutdown.assert_called_once()

    def test_stop_vm_already_off(self):
        conn = MagicMock()
        dom = MagicMock()
        dom.isActive.return_value = 0
        conn.lookupByName.return_value = dom
        stop_vm(conn, "vm")
        dom.shutdown.assert_not_called()

    def test_destroy_vm(self):
        conn = MagicMock()
        dom = MagicMock()
        dom.isActive.return_value = 1
        conn.lookupByName.return_value = dom
        destroy_vm(conn, "vm")
        dom.destroy.assert_called_once()

    def test_destroy_vm_already_off(self):
        conn = MagicMock()
        dom = MagicMock()
        dom.isActive.return_value = 0
        conn.lookupByName.return_value = dom
        destroy_vm(conn, "vm")
        dom.destroy.assert_not_called()


class TestRebootReset:
    def test_reboot_vm(self):
        conn = MagicMock()
        dom = MagicMock()
        dom.isActive.return_value = 1
        conn.lookupByName.return_value = dom
        reboot_vm(conn, "vm")
        dom.reboot.assert_called_once_with(0)

    def test_reboot_vm_not_running(self):
        conn = MagicMock()
        dom = MagicMock()
        dom.isActive.return_value = 0
        conn.lookupByName.return_value = dom
        with pytest.raises(InfrastructureError, match="not running"):
            reboot_vm(conn, "vm")

    def test_reset_vm(self):
        conn = MagicMock()
        dom = MagicMock()
        dom.isActive.return_value = 1
        conn.lookupByName.return_value = dom
        reset_vm(conn, "vm")
        dom.reset.assert_called_once()

    def test_reset_vm_not_running(self):
        conn = MagicMock()
        dom = MagicMock()
        dom.isActive.return_value = 0
        conn.lookupByName.return_value = dom
        with pytest.raises(InfrastructureError, match="not running"):
            reset_vm(conn, "vm")


class TestUndefineVM:
    def test_undefine_with_storage(self):
        conn = MagicMock()
        dom = MagicMock()
        dom.isActive.return_value = 0
        dom.XMLDesc.return_value = """<domain><devices>
            <disk type='file' device='disk'>
                <source file='/path/to/disk.qcow2'/>
            </disk>
        </devices></domain>"""
        conn.lookupByName.return_value = dom

        with patch("app.infrastructure.libvirt_driver._remove_storage") as mock_rm:
            undefine_vm(conn, "vm")
            dom.undefineFlags.assert_called_once_with(libvirt.VIR_DOMAIN_UNDEFINE_SNAPSHOTS_METADATA)
            mock_rm.assert_called_once_with("/path/to/disk.qcow2")

    def test_undefine_without_storage(self):
        conn = MagicMock()
        dom = MagicMock()
        dom.isActive.return_value = 0
        conn.lookupByName.return_value = dom

        undefine_vm(conn, "vm", remove_storage=False)
        dom.undefineFlags.assert_called_once_with(libvirt.VIR_DOMAIN_UNDEFINE_SNAPSHOTS_METADATA)


class TestDiskOperations:
    def test_attach_disk(self):
        conn = MagicMock()
        dom = MagicMock()
        conn.lookupByName.return_value = dom
        attach_disk(conn, "vm", "/path/test.qcow2")
        dom.attachDevice.assert_called_once()
        assert "source file='/path/test.qcow2'" in dom.attachDevice.call_args[0][0]
        assert "target dev='vdb'" in dom.attachDevice.call_args[0][0]

    def test_attach_disk_custom_dev(self):
        conn = MagicMock()
        dom = MagicMock()
        conn.lookupByName.return_value = dom
        attach_disk(conn, "vm", "/path/test.qcow2", target_dev="vdc", bus="virtio")
        assert "target dev='vdc'" in dom.attachDevice.call_args[0][0]

    def test_detach_disk(self):
        conn = MagicMock()
        dom = MagicMock()
        conn.lookupByName.return_value = dom
        detach_disk(conn, "vm", "vdb")
        dom.detachDevice.assert_called_once()

    def test_attach_iso(self):
        conn = MagicMock()
        dom = MagicMock()
        conn.lookupByName.return_value = dom
        attach_iso(conn, "vm", "/iso/debian.iso")
        dom.attachDevice.assert_called_once()
        assert "device='cdrom'" in dom.attachDevice.call_args[0][0]
        assert "source file='/iso/debian.iso'" in dom.attachDevice.call_args[0][0]

    def test_detach_iso(self):
        conn = MagicMock()
        dom = MagicMock()
        conn.lookupByName.return_value = dom
        detach_iso(conn, "vm")
        dom.detachDevice.assert_called_once()

    def test_create_disk(self):
        with patch("subprocess.check_call") as mock_qemu:
            create_disk("/pool/new.qcow2", 20)
            mock_qemu.assert_called_once()
            assert "new.qcow2" in " ".join(mock_qemu.call_args[0][0])
            assert "20G" in " ".join(mock_qemu.call_args[0][0])

    def test_create_disk_failure(self):
        import subprocess
        with patch("subprocess.check_call", side_effect=subprocess.CalledProcessError(1, "qemu-img")):
            with pytest.raises(InfrastructureError):
                create_disk("/pool/fail.qcow2", 10)


class TestSnapshots:
    def test_snapshot_create(self):
        conn = MagicMock()
        dom = MagicMock()
        conn.lookupByName.return_value = dom
        snapshot_create(conn, "vm", "snap1")
        dom.snapshotCreateXML.assert_called_once()
        assert "<name>snap1</name>" in dom.snapshotCreateXML.call_args[0][0]

    def test_snapshot_list(self):
        conn = MagicMock()
        dom = MagicMock()
        snap1 = MagicMock()
        snap1.getName.return_value = "snap1"
        snap1.getXMLDesc.return_value = "<domainsnapshot><creationTime>1700000000</creationTime></domainsnapshot>"
        dom.listAllSnapshots.return_value = [snap1]
        conn.lookupByName.return_value = dom

        snaps = snapshot_list(conn, "vm")
        assert len(snaps) == 1
        assert snaps[0]["name"] == "snap1"
        assert snaps[0]["created"] != ""

    def test_snapshot_list_empty(self):
        conn = MagicMock()
        dom = MagicMock()
        dom.listAllSnapshots.return_value = []
        conn.lookupByName.return_value = dom
        assert snapshot_list(conn, "vm") == []

    def test_snapshot_revert(self):
        conn = MagicMock()
        dom = MagicMock()
        snap = MagicMock()
        dom.snapshotLookupByName.return_value = snap
        conn.lookupByName.return_value = dom
        snapshot_revert(conn, "vm", "snap1")
        dom.revertToSnapshot.assert_called_once_with(snap)

    def test_snapshot_delete(self):
        conn = MagicMock()
        dom = MagicMock()
        snap = MagicMock()
        dom.snapshotLookupByName.return_value = snap
        conn.lookupByName.return_value = dom
        snapshot_delete(conn, "vm", "snap1")
        snap.delete.assert_called_once()


class TestVNC:
    def test_get_vnc_port_active(self):
        conn = MagicMock()
        dom = MagicMock()
        dom.isActive.return_value = 1
        dom.XMLDesc.return_value = """<domain>
            <devices>
                <graphics type='vnc' port='5900' autoport='yes'/>
            </devices>
        </domain>"""
        conn.lookupByName.return_value = dom
        port = get_vnc_port(conn, "vm")
        assert port == 5900

    def test_get_vnc_port_not_active(self):
        conn = MagicMock()
        dom = MagicMock()
        dom.isActive.return_value = 0
        conn.lookupByName.return_value = dom
        port = get_vnc_port(conn, "vm")
        assert port is None

    def test_get_vnc_port_no_graphics(self):
        conn = MagicMock()
        dom = MagicMock()
        dom.isActive.return_value = 1
        dom.XMLDesc.return_value = "<domain><name>test</name></domain>"
        conn.lookupByName.return_value = dom
        port = get_vnc_port(conn, "vm")
        assert port is None

    def test_get_vnc_port_autoport(self):
        conn = MagicMock()
        dom = MagicMock()
        dom.isActive.return_value = 1
        dom.XMLDesc.return_value = """<domain>
            <devices>
                <graphics type='vnc' port='-1' autoport='yes'/>
            </devices>
        </domain>"""
        conn.lookupByName.return_value = dom
        port = get_vnc_port(conn, "vm")
        assert port is None


class TestXMLAndDomain:
    def test_get_domain_xml(self):
        conn = MagicMock()
        dom = MagicMock()
        dom.XMLDesc.return_value = "<domain><name>vm</name></domain>"
        conn.lookupByName.return_value = dom
        xml = get_domain_xml(conn, "vm")
        assert "<name>vm</name>" in xml

    def test_rename_in_xml(self):
        xml = "<domain><name>old-vm</name><uuid>abc123</uuid></domain>"
        new_xml = rename_in_xml(xml, "new-vm")
        assert "<name>new-vm</name>" in new_xml
        assert "<name>old-vm</name>" not in new_xml
        assert "<uuid>" in new_xml
        assert "abc123" not in new_xml


class TestNetworkOps:
    def test_network_create_nat(self):
        conn = MagicMock()
        net = MagicMock()
        conn.networkDefineXML.return_value = net
        conn.networkLookupByName.return_value = net
        network_create_nat(conn, "test-net", "virbr1", "10.0.0.0/24")
        conn.networkDefineXML.assert_called_once()
        xml = conn.networkDefineXML.call_args[0][0]
        assert "<name>test-net</name>" in xml
        assert "10.0.0.0" in xml  # network address from subnet prefix
        assert "prefix='24'" in xml
        net.setAutostart.assert_called_once_with(True)
        net.create.assert_called_once()

    def test_network_list(self):
        conn = MagicMock()
        net = MagicMock()
        net.name.return_value = "default"
        net.isActive.return_value = 1
        net.autostart.return_value = 1
        net.XMLDesc.return_value = """<network>
            <name>default</name>
            <bridge name='virbr0'/>
            <ip address='192.168.122.1' prefix='24'/>
        </network>"""
        conn.listAllNetworks.return_value = [net]

        nets = network_list(conn)
        assert len(nets) == 1
        assert nets[0]["name"] == "default"
        assert nets[0]["bridge"] == "virbr0"
        assert nets[0]["subnet"] == "192.168.122.1/24"

    def test_network_delete(self):
        conn = MagicMock()
        net = MagicMock()
        net.isActive.return_value = 1
        conn.networkLookupByName.return_value = net
        network_delete(conn, "test-net")
        net.destroy.assert_called_once()
        net.undefine.assert_called_once()

    def test_network_leases(self):
        conn = MagicMock()
        net = MagicMock()
        net.isActive.return_value = 1
        net.name.return_value = "default"
        net.DHCPLeases.return_value = [{
            "ipaddr": "192.168.122.10",
            "mac": "52:54:00:aa:bb:cc",
            "hostname": "test-vm",
            "prefix": 24,
            "expirytime": 1700000000,
            "type": 0,
        }]
        conn.listAllNetworks.return_value = [net]

        leases = network_leases(conn)
        assert len(leases) == 1
        assert leases[0]["ip"] == "192.168.122.10"
        assert leases[0]["hostname"] == "test-vm"

    def test_network_leases_empty(self):
        conn = MagicMock()
        net = MagicMock()
        net.isActive.return_value = 0
        conn.listAllNetworks.return_value = [net]
        assert network_leases(conn) == []


class TestGuestAgent:
    def test_guest_agent_ip_found(self):
        conn = MagicMock()
        dom = MagicMock()
        dom.isActive.return_value = 1
        dom.interfaceAddresses.return_value = [
            {"name": "eth0", "addrs": [
                {"type": libvirt.VIR_IP_ADDR_TYPE_IPV4, "addr": "192.168.122.42"},
            ]},
        ]
        conn.lookupByName.return_value = dom
        ip = guest_agent_ip(conn, "vm")
        assert ip == "192.168.122.42"

    def test_guest_agent_ip_not_active(self):
        conn = MagicMock()
        dom = MagicMock()
        dom.isActive.return_value = 0
        conn.lookupByName.return_value = dom
        assert guest_agent_ip(conn, "vm") is None

    def test_guest_agent_ip_no_agent(self):
        conn = MagicMock()
        dom = MagicMock()
        dom.isActive.return_value = 1
        dom.interfaceAddresses.side_effect = libvirt.libvirtError("no agent")
        conn.lookupByName.return_value = dom
        ip = guest_agent_ip(conn, "vm")
        assert ip is None

    def test_guest_agent_ip_only_loopback(self):
        conn = MagicMock()
        dom = MagicMock()
        dom.isActive.return_value = 1
        dom.interfaceAddresses.return_value = [
            {"name": "lo", "addrs": [
                {"type": libvirt.VIR_IP_ADDR_TYPE_IPV4, "addr": "127.0.0.1"},
            ]},
        ]
        conn.lookupByName.return_value = dom
        assert guest_agent_ip(conn, "vm") is None

    def test_guest_agent_ip_no_attribute(self):
        conn = MagicMock()
        dom = MagicMock()
        dom.isActive.return_value = 1
        dom.interfaceAddresses.side_effect = AttributeError("VIR_DOMAIN_INTERFACE_ADDRESSES_SOURCE_AGENT not available")
        conn.lookupByName.return_value = dom
        assert guest_agent_ip(conn, "vm") is None


class TestMetrics:
    def test_get_metrics(self):
        conn = MagicMock()
        dom = MagicMock()
        dom.info.return_value = (1, 4194304, 2097152, 2, 5000000000)
        dom.memoryStats.return_value = {"available": 4194304, "unused": 2097152}
        dom.XMLDesc.return_value = """<domain>
            <devices>
                <disk type='file' device='disk'>
                    <target dev='vda' bus='virtio'/>
                </disk>
            </devices>
        </domain>"""
        dom.blockStats.return_value = (100, 1024000, 50, 512000)
        conn.lookupByName.return_value = dom

        metrics = get_metrics(conn, "vm")
        assert metrics["state"] == "running"
        assert metrics["max_memory_mb"] == 4096  # 4194304 KiB / 1024
        assert metrics["cpu_count"] == 2
        assert metrics["cpu_time_s"] == 5.0
        assert "memory_stats" in metrics
        assert "vda" in metrics["block_stats"]
        assert metrics["block_stats"]["vda"]["rd_req"] == 100

    def test_get_metrics_stopped(self):
        conn = MagicMock()
        dom = MagicMock()
        dom.info.return_value = (5, 2097152, 0, 1, 0)
        conn.lookupByName.return_value = dom
        metrics = get_metrics(conn, "vm")
        assert metrics["state"] == "stopped"


class TestCopyDisk:
    def test_copy_disk_image(self):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0
            copy_disk_image("/src.qcow2", "/dst.qcow2")
            args = mock_run.call_args[0][0]
            assert "convert" in args
            assert "/src.qcow2" in args
            assert "/dst.qcow2" in args

    def test_copy_disk_retry_fails(self):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value.returncode = 1
            with pytest.raises(InfrastructureError, match="3 attempts"):
                copy_disk_image("/src.qcow2", "/dst.qcow2")

    def test_copy_disk_timeout(self):
        with patch("subprocess.run", side_effect=TimeoutExpired("qemu-img", 120)):
            with pytest.raises(InfrastructureError, match="timed out"):
                copy_disk_image("/src.qcow2", "/dst.qcow2")


class TestSetVCpus:
    def test_set_vcpus_active(self):
        conn = MagicMock()
        dom = MagicMock()
        dom.isActive.return_value = 1
        conn.lookupByName.return_value = dom
        set_vcpus(conn, "vm", 4)
        dom.setVcpus.assert_called_once_with(4)

    def test_set_vcpus_inactive(self):
        conn = MagicMock()
        dom = MagicMock()
        dom.isActive.return_value = 0
        dom.XMLDesc.return_value = "<domain><vcpu>2</vcpu></domain>"
        conn.lookupByName.return_value = dom
        set_vcpus(conn, "vm", 8)
        # When inactive, it calls dom.undefine() + conn.defineXML(new_xml)
        conn.defineXML.assert_called_once()
        assert "8" in conn.defineXML.call_args[0][0]


class TestSetMemory:
    def test_set_memory_active(self):
        conn = MagicMock()
        dom = MagicMock()
        dom.isActive.return_value = 1
        conn.lookupByName.return_value = dom
        set_memory(conn, "vm", 2097152)
        dom.setMemory.assert_called_once_with(2097152)


class TestBlockResize:
    def test_block_resize(self):
        conn = MagicMock()
        dom = MagicMock()
        conn.lookupByName.return_value = dom
        block_resize(conn, "vm", "vda", 10485760)
        dom.blockResize.assert_called_once_with("vda", 10485760)


class TestClose:
    def test_close(self):
        conn = MagicMock()
        close(conn)
        conn.close.assert_called_once()

    def test_close_exception(self):
        conn = MagicMock()
        conn.close.side_effect = Exception("fail")
        close(conn)  # should not raise


class TestExtractCreationTime:
    def test_valid_timestamp(self):
        xml = "<domainsnapshot><creationTime>1700000000</creationTime></domainsnapshot>"
        dt = _extract_creation_time(xml)
        assert dt == "2023-11-14T22:13:20+00:00"

    def test_no_timestamp(self):
        xml = "<domainsnapshot><name>snap1</name></domainsnapshot>"
        assert _extract_creation_time(xml) == ""

    def test_garbage_xml(self):
        assert _extract_creation_time("not xml") == ""


from subprocess import TimeoutExpired
