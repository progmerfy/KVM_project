from fastapi.testclient import TestClient
from unittest.mock import MagicMock
import app.infrastructure.libvirt_driver as driver
from app.errors import InfrastructureError
from app.main import app

client = TestClient(app)


def test_create_vm_success(monkeypatch):
    # mock storage
    monkeypatch.setattr(
        "app.infrastructure.storage.prepare_disk",
        lambda img, name, gb: f"/tmp/{name}.qcow2",
    )

    # mock libvirt driver
    mock_conn = MagicMock()
    monkeypatch.setattr(
        "app.infrastructure.libvirt_driver.connect", lambda uri: mock_conn
    )
    monkeypatch.setattr(
        "app.infrastructure.libvirt_driver.define_vm", lambda conn, xml: "vm-test"
    )
    monkeypatch.setattr(
        "app.infrastructure.libvirt_driver.start_vm", lambda conn, domain: None
    )

    resp = client.post(
        "/vm/create",
        json={
            "name": "vm-test",
            "image": "/img/base.qcow2",
            "cpu": 1,
            "memory_mb": 256,
            "disk_gb": 5,
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["vm"]["name"] == "vm-test"


def test_create_vm_image_not_found(monkeypatch):
    def raise_not_found(img, name, gb):
        raise FileNotFoundError(f"base image not found: {img}")

    monkeypatch.setattr("app.infrastructure.storage.prepare_disk", raise_not_found)

    resp = client.post(
        "/vm/create",
        json={
            "name": "vm-missing",
            "image": "/img/missing.qcow2",
            "cpu": 1,
            "memory_mb": 256,
            "disk_gb": 5,
        },
    )
    assert resp.status_code == 400
    assert resp.json()["detail"]["code"] == "IMAGE_NOT_FOUND"


def test_create_vm_infrastructure_error(monkeypatch):
    monkeypatch.setattr(
        "app.infrastructure.storage.prepare_disk",
        lambda img, name, gb: f"/tmp/{name}.qcow2",
    )
    # make connect raise InfrastructureError
    monkeypatch.setattr(
        "app.infrastructure.libvirt_driver.connect",
        lambda uri: (_ for _ in ()).throw(InfrastructureError("libvirt down")),
    )

    resp = client.post(
        "/vm/create",
        json={
            "name": "vm-fail",
            "image": "/img/base.qcow2",
            "cpu": 1,
            "memory_mb": 256,
            "disk_gb": 5,
        },
    )
    assert resp.status_code == 503
    assert resp.json()["detail"]["code"] == "InfrastructureError"


def test_status_not_found(monkeypatch):
    mock_conn = MagicMock()
    mock_conn.lookupByName.side_effect = Exception("not found")
    monkeypatch.setattr(
        "app.infrastructure.libvirt_driver.connect", lambda uri: mock_conn
    )

    resp = client.get("/vm/status/noexist")
    assert resp.status_code == 404
    assert resp.json()["detail"]["code"] == "VM_NOT_FOUND"


def test_list_vms(monkeypatch):
    mock_conn = MagicMock()
    dom1 = MagicMock()
    dom1.name.return_value = "vm1"
    dom1.isActive.return_value = 1
    dom2 = MagicMock()
    dom2.name.return_value = "vm2"
    dom2.isActive.return_value = 0
    mock_conn.listAllDomains.return_value = [dom1, dom2]
    monkeypatch.setattr(
        "app.infrastructure.libvirt_driver.connect", lambda uri: mock_conn
    )

    resp = client.get("/vm/list")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert any(v["name"] == "vm1" for v in body["vms"])


def test_start_stop_delete(monkeypatch):
    mock_conn = MagicMock()
    monkeypatch.setattr(
        "app.infrastructure.libvirt_driver.connect", lambda uri: mock_conn
    )
    monkeypatch.setattr(
        "app.infrastructure.libvirt_driver.start_vm", lambda conn, name: None
    )
    monkeypatch.setattr(
        "app.infrastructure.libvirt_driver.stop_vm", lambda conn, name: None
    )
    monkeypatch.setattr(
        "app.infrastructure.libvirt_driver.undefine_vm",
        lambda conn, name, remove_storage=True: None,
    )

    resp = client.post("/vm/start", json={"name": "vm1"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"

    resp = client.post("/vm/stop", json={"name": "vm1"})
    assert resp.status_code == 200

    resp = client.request("DELETE", "/vm/delete", json={"name": "vm1"})
    assert resp.status_code == 200
