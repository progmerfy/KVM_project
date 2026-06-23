"""Unit tests for app.infrastructure.network — MAC gen, default network, IP lookup."""

import pytest
from unittest.mock import patch, MagicMock, PropertyMock

from app.infrastructure.network import generate_mac, ensure_default_network, get_vm_ip


class TestGenerateMAC:
    def test_format(self):
        mac = generate_mac()
        assert len(mac.split(":")) == 6
        for part in mac.split(":"):
            assert len(part) == 2
            int(part, 16)

    def test_prefix(self):
        mac = generate_mac()
        assert mac.startswith("52:54:00:")

    def test_random_last_three(self):
        macs = {generate_mac() for _ in range(100)}
        # Should have at least some variation (extremely unlikely to be all 1)
        assert len(macs) > 1


class TestEnsureDefaultNetwork:
    def test_network_exists_and_active(self):
        conn = MagicMock()
        net = MagicMock()
        net.isActive.return_value = 1
        net.bridgeName.return_value = "virbr0"
        conn.networkLookupByName.return_value = net

        result = ensure_default_network(conn)
        assert result["name"] == "default"
        assert result["bridge"] == "virbr0"
        assert result["active"] is True
        conn.networkDefineXML.assert_not_called()

    def test_network_exists_inactive(self):
        conn = MagicMock()
        net = MagicMock()
        net.isActive.return_value = 0
        net.bridgeName.return_value = "virbr0"
        conn.networkLookupByName.return_value = net

        result = ensure_default_network(conn)
        assert result["active"] is True
        net.create.assert_called_once()

    def test_network_created(self):
        conn = MagicMock()
        conn.networkLookupByName.side_effect = Exception("not found")
        net = MagicMock()
        net.isActive.return_value = 1
        net.bridgeName.return_value = "virbr0"
        conn.networkDefineXML.return_value = net

        result = ensure_default_network(conn)
        assert result["name"] == "default"
        conn.networkDefineXML.assert_called_once()
        assert "<name>default</name>" in conn.networkDefineXML.call_args[0][0]

    def test_network_create_fails(self):
        conn = MagicMock()
        conn.networkLookupByName.side_effect = Exception("not found")
        conn.networkDefineXML.return_value = None

        from app.errors import InfrastructureError
        with pytest.raises(InfrastructureError):
            ensure_default_network(conn)


class TestGetVMIP:
    def test_vm_not_found(self):
        conn = MagicMock()
        conn.lookupByName.side_effect = Exception("not found")
        ip = get_vm_ip(conn, "nonexistent")
        assert ip is None

    def test_vm_not_active(self):
        conn = MagicMock()
        dom = MagicMock()
        dom.isActive.return_value = 0
        conn.lookupByName.return_value = dom

        ip = get_vm_ip(conn, "stopped-vm")
        assert ip is None

    def test_vm_has_ip(self):
        conn = MagicMock()
        dom = MagicMock()
        dom.isActive.return_value = 1

        # Simulate MACs in XML
        dom.XMLDesc.return_value = """
        <domain>
          <devices>
            <interface type='network'>
              <mac address='52:54:00:aa:bb:cc'/>
            </interface>
          </devices>
        </domain>
        """

        # Simulate network list
        conn.listNetworks.return_value = ["default"]
        conn.listDefinedNetworks.return_value = []

        # Simulate DHCP lease
        net = MagicMock()
        net.DHCPLeases.return_value = [{"ipaddr": "192.168.122.42"}]
        conn.networkLookupByName.return_value = net

        conn.lookupByName.return_value = dom

        ip = get_vm_ip(conn, "running-vm")
        assert ip == "192.168.122.42"

    def test_vm_no_leases(self):
        conn = MagicMock()
        dom = MagicMock()
        dom.isActive.return_value = 1
        dom.XMLDesc.return_value = """
        <domain>
          <devices>
            <interface type='network'>
              <mac address='52:54:00:11:22:33'/>
            </interface>
          </devices>
        </domain>
        """
        conn.listNetworks.return_value = ["default"]
        conn.listDefinedNetworks.return_value = []
        net = MagicMock()
        net.DHCPLeases.return_value = []
        conn.networkLookupByName.return_value = net
        conn.lookupByName.return_value = dom

        ip = get_vm_ip(conn, "no-lease")
        assert ip is None

    def test_vm_no_macs(self):
        conn = MagicMock()
        dom = MagicMock()
        dom.isActive.return_value = 1
        dom.XMLDesc.return_value = "<domain><name>test</name></domain>"
        conn.lookupByName.return_value = dom

        ip = get_vm_ip(conn, "no-macs")
        assert ip is None

    def test_network_lookup_fails(self):
        conn = MagicMock()
        dom = MagicMock()
        dom.isActive.return_value = 1
        dom.XMLDesc.return_value = """
        <domain>
          <devices>
            <interface type='network'>
              <mac address='52:54:00:11:22:33'/>
            </interface>
          </devices>
        </domain>
        """
        conn.listNetworks.return_value = ["default"]
        conn.listDefinedNetworks.return_value = []
        conn.networkLookupByName.side_effect = Exception("net error")
        conn.lookupByName.return_value = dom

        ip = get_vm_ip(conn, "net-error")
        assert ip is None
