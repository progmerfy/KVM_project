from unittest.mock import MagicMock, patch
from app.services.vm_manager import get_vm_status


def test_get_vm_status_not_found():
    mock_conn = MagicMock()
    mock_conn.lookupByName.side_effect = Exception("not found")
    with patch("app.infrastructure.libvirt_driver.connect", return_value=mock_conn):
        status = get_vm_status("noexist", None)
        assert status == "not-found"


def test_get_vm_status_running_and_stopped():
    mock_conn = MagicMock()
    dom_running = MagicMock()
    dom_running.isActive.return_value = 1
    dom_stopped = MagicMock()
    dom_stopped.isActive.return_value = 0

    # first call returns running, second returns stopped
    mock_conn.lookupByName.side_effect = [dom_running, dom_stopped]
    with patch("app.infrastructure.libvirt_driver.connect", return_value=mock_conn):
        assert get_vm_status("vm1", None) == "running"
        assert get_vm_status("vm2", None) == "stopped"
