from fastapi.testclient import TestClient
from unittest.mock import MagicMock, patch
from app.errors import InfrastructureError
from app.main import app

client = TestClient(app)


def test_create_vm_success(monkeypatch):
    monkeypatch.setattr(
        "app.infrastructure.storage.prepare_disk",
        lambda img, name, gb: f"/tmp/{name}.qcow2",
    )
    monkeypatch.setattr(
        "app.infrastructure.network.ensure_default_network",
        lambda conn: {"name": "default", "bridge": "virbr0", "active": True},
    )
    monkeypatch.setattr(
        "app.infrastructure.network.get_vm_ip",
        lambda conn, name: "192.168.122.42",
    )
    monkeypatch.setattr(
        "app.services.cloud_init.build_cloudinit_iso",
        lambda **kw: "/tmp/ci.iso",
    )

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
    assert resp.status_code == 202
    body = resp.json()
    assert body["status"] == "accepted"
    assert body["vm"]["name"] == "vm-test"
    assert body["vm"]["ip_address"] == "192.168.122.42"


def test_create_vm_with_cloud_init(monkeypatch):
    monkeypatch.setattr(
        "app.infrastructure.storage.prepare_disk",
        lambda img, name, gb: f"/tmp/{name}.qcow2",
    )
    monkeypatch.setattr(
        "app.infrastructure.network.ensure_default_network",
        lambda conn: {"name": "default", "bridge": "virbr0", "active": True},
    )
    monkeypatch.setattr(
        "app.infrastructure.network.get_vm_ip",
        lambda conn, name: "192.168.122.100",
    )
    monkeypatch.setattr(
        "app.services.cloud_init.build_cloudinit_iso",
        lambda **kw: "/tmp/ci.iso",
    )

    mock_conn = MagicMock()
    monkeypatch.setattr(
        "app.infrastructure.libvirt_driver.connect", lambda uri: mock_conn
    )
    monkeypatch.setattr(
        "app.infrastructure.libvirt_driver.define_vm", lambda conn, xml: "vm-ci"
    )
    monkeypatch.setattr(
        "app.infrastructure.libvirt_driver.start_vm", lambda conn, domain: None
    )

    resp = client.post(
        "/vm/create",
        json={
            "name": "vm-ci",
            "image": "/img/ubuntu.qcow2",
            "cpu": 2,
            "memory_mb": 2048,
            "disk_gb": 20,
            "cloud_init_ssh_key": "ssh-rsa AAAAB3... user@host",
            "cloud_init_user": "admin",
        },
    )
    assert resp.status_code == 202
    body = resp.json()
    assert body["vm"]["cloud_init"] is True
    assert body["vm"]["ip_address"] == "192.168.122.100"


def test_create_vm_with_iso(monkeypatch):
    monkeypatch.setattr(
        "app.infrastructure.storage.prepare_disk",
        lambda img, name, gb: f"/tmp/{name}.qcow2",
    )
    monkeypatch.setattr(
        "app.infrastructure.network.ensure_default_network",
        lambda conn: {"name": "default", "bridge": "virbr0", "active": True},
    )
    monkeypatch.setattr(
        "app.infrastructure.network.get_vm_ip",
        lambda conn, name: "192.168.122.42",
    )

    mock_conn = MagicMock()
    monkeypatch.setattr(
        "app.infrastructure.libvirt_driver.connect", lambda uri: mock_conn
    )
    monkeypatch.setattr(
        "app.infrastructure.libvirt_driver.define_vm", lambda conn, xml: "vm-test-iso"
    )
    monkeypatch.setattr(
        "app.infrastructure.libvirt_driver.start_vm", lambda conn, domain: None
    )

    resp = client.post(
        "/vm/create",
        json={
            "name": "vm-test-iso",
            "image": "/img/base.qcow2",
            "iso_path": "/iso/ubuntu.iso",
            "cpu": 2,
            "memory_mb": 2048,
            "disk_gb": 20,
        },
    )
    assert resp.status_code == 202
    body = resp.json()
    assert body["vm"]["ip_address"] == "192.168.122.42"


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
    monkeypatch.setattr(
        "app.infrastructure.network.ensure_default_network",
        lambda conn: {"name": "default", "bridge": "virbr0", "active": True},
    )
    monkeypatch.setattr(
        "app.infrastructure.network.get_vm_ip",
        lambda conn, name: "192.168.122.42",
    )
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
    monkeypatch.setattr(
        "app.infrastructure.network.get_vm_ip",
        lambda conn, name: "192.168.122.42" if name == "vm1" else None,
    )

    resp = client.get("/vm/list")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    vms = body["vms"]
    assert any(v["name"] == "vm1" for v in vms)
    for v in vms:
        if v["name"] == "vm1":
            assert v["ip_address"] == "192.168.122.42"


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


def test_reboot_vm(monkeypatch):
    mock_conn = MagicMock()
    monkeypatch.setattr(
        "app.infrastructure.libvirt_driver.connect", lambda uri: mock_conn
    )
    monkeypatch.setattr(
        "app.infrastructure.libvirt_driver.reboot_vm", lambda conn, name: None
    )

    resp = client.post("/vm/reboot", json={"name": "vm1"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_reset_vm(monkeypatch):
    mock_conn = MagicMock()
    monkeypatch.setattr(
        "app.infrastructure.libvirt_driver.connect", lambda uri: mock_conn
    )
    monkeypatch.setattr(
        "app.infrastructure.libvirt_driver.reset_vm", lambda conn, name: None
    )

    resp = client.post("/vm/reset", json={"name": "vm1"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_attach_iso(monkeypatch):
    mock_conn = MagicMock()
    monkeypatch.setattr(
        "app.infrastructure.libvirt_driver.connect", lambda uri: mock_conn
    )
    monkeypatch.setattr(
        "app.infrastructure.libvirt_driver.attach_iso",
        lambda conn, name, iso_path: None,
    )

    resp = client.post(
        "/vm/attach-iso",
        json={"name": "vm1", "iso_path": "/iso/debian.iso"},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_detach_iso(monkeypatch):
    mock_conn = MagicMock()
    monkeypatch.setattr(
        "app.infrastructure.libvirt_driver.connect", lambda uri: mock_conn
    )
    monkeypatch.setattr(
        "app.infrastructure.libvirt_driver.detach_iso",
        lambda conn, name: None,
    )

    resp = client.post(
        "/vm/detach-iso",
        json={"name": "vm1"},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_get_vm_info_with_ip(monkeypatch):
    from app.infrastructure import libvirt_driver

    mock_conn = MagicMock()
    dom = MagicMock()
    dom.isActive.return_value = 1
    mock_conn.lookupByName.return_value = dom
    monkeypatch.setattr(
        "app.infrastructure.libvirt_driver.connect", lambda uri: mock_conn
    )
    monkeypatch.setattr(
        "app.infrastructure.libvirt_driver.get_domain_xml",
        lambda conn, name, flags: (
            "<domain><memory unit='MiB'>2048</memory><vcpu>4</vcpu></domain>"
        ),
    )
    monkeypatch.setattr(
        "app.infrastructure.network.get_vm_ip",
        lambda conn, name: "10.0.0.15",
    )

    resp = client.get("/vm/info/test-vm")
    assert resp.status_code == 200
    body = resp.json()
    assert body["vm"]["ip_address"] == "10.0.0.15"
    assert body["vm"]["state"] == "running"
    assert body["vm"]["memory_mb"] == 2048
    assert body["vm"]["cpu"] == 4


def test_health_check():
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_images_list(monkeypatch):
    from app.models.image import ImageInfo
    monkeypatch.setattr(
        "app.services.image_manager.list_images",
        lambda: [
            ImageInfo(
                name="ubuntu.qcow2",
                path="/images/ubuntu.qcow2",
                format="qcow2",
                virtual_size_gb=10.0,
                actual_size_bytes=536870912,
            )
        ],
    )

    resp = client.get("/images/list")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["images"]) == 1
    assert body["images"][0]["name"] == "ubuntu.qcow2"


def test_images_cloud_list():
    resp = client.get("/images/cloud/list")
    assert resp.status_code == 200
    body = resp.json()
    assert "ubuntu-24.04" in body["cloud_images"]


def test_images_get(monkeypatch):
    from app.models.image import ImageInfo
    monkeypatch.setattr(
        "app.services.image_manager.get_image",
        lambda name: ImageInfo(
            name=name,
            path=f"/images/{name}",
            format="qcow2",
            virtual_size_gb=20.0,
            actual_size_bytes=1073741824,
        ),
    )

    resp = client.get("/images/test.qcow2")
    assert resp.status_code == 200
    assert resp.json()["image"]["name"] == "test.qcow2"


def test_images_get_not_found(monkeypatch):
    monkeypatch.setattr(
        "app.services.image_manager.get_image", lambda name: None
    )

    resp = client.get("/images/nonexist.qcow2")
    assert resp.status_code == 404


def test_images_delete(monkeypatch):
    monkeypatch.setattr(
        "app.services.image_manager.delete_image", lambda name: None
    )

    resp = client.delete("/images/test.qcow2")
    assert resp.status_code == 200


def test_host_info(monkeypatch):
    monkeypatch.setattr(
        "app.services.host_manager.get_host_info",
        lambda: {
            "hostname": "node1",
            "cpu": {"cores": 8, "model": "Intel"},
            "memory": {"total_mb": 16384, "total_gb": 16.0},
            "storage": [],
        },
    )

    resp = client.get("/host/info")
    assert resp.status_code == 200
    body = resp.json()
    assert body["host"]["hostname"] == "node1"


def test_host_stats(monkeypatch):
    monkeypatch.setattr(
        "app.services.host_manager.get_host_stats",
        lambda: {
            "cpu": {"used_percent": 25.0, "idle_percent": 75.0},
            "memory": {"total_mb": 16384, "used_percent": 40.0},
            "storage": [],
        },
    )

    resp = client.get("/host/stats")
    assert resp.status_code == 200
    assert resp.json()["stats"]["cpu"]["used_percent"] == 25.0


def test_images_storage_info(monkeypatch):
    monkeypatch.setattr(
        "app.api.image_routes._get_image_dir", lambda: "/tmp"
    )

    resp = client.get("/images/storage/info")
    assert resp.status_code == 200
    assert "storage" in resp.json()


def test_images_download_cloud(monkeypatch):
    from app.models.image import ImageInfo
    monkeypatch.setattr(
        "app.services.image_manager.download_cloud_image",
        lambda name: ImageInfo(
            name="noble-server-cloudimg-amd64.img",
            path="/images/noble-server-cloudimg-amd64.img",
            format="qcow2",
            virtual_size_gb=10.0,
            actual_size_bytes=536870912,
        ),
    )

    resp = client.post("/images/download-cloud?name=ubuntu-24.04")
    assert resp.status_code == 200
    assert resp.json()["image"]["name"] == "noble-server-cloudimg-amd64.img"


def test_vnc_info_running(monkeypatch):
    mock_conn = MagicMock()
    dom = MagicMock()
    dom.isActive.return_value = 1
    mock_conn.lookupByName.return_value = dom
    monkeypatch.setattr(
        "app.infrastructure.libvirt_driver.connect", lambda uri: mock_conn
    )
    monkeypatch.setattr(
        "app.infrastructure.libvirt_driver.get_vnc_port", lambda conn, name: 5901
    )

    resp = client.get("/vm/vnc/info/test-vm")
    assert resp.status_code == 200
    body = resp.json()
    assert body["vnc"]["vnc_port"] == 5901
    assert body["vnc"]["state"] == "running"


def test_vnc_info_not_found(monkeypatch):
    mock_conn = MagicMock()
    mock_conn.lookupByName.side_effect = Exception("not found")
    monkeypatch.setattr(
        "app.infrastructure.libvirt_driver.connect", lambda uri: mock_conn
    )

    resp = client.get("/vm/vnc/info/noexist")
    assert resp.status_code == 404


def test_vnc_console_page(monkeypatch):
    mock_conn = MagicMock()
    dom = MagicMock()
    dom.isActive.return_value = 1
    mock_conn.lookupByName.return_value = dom
    monkeypatch.setattr(
        "app.infrastructure.libvirt_driver.connect", lambda uri: mock_conn
    )
    monkeypatch.setattr(
        "app.infrastructure.libvirt_driver.get_vnc_port", lambda conn, name: 5901
    )

    resp = client.get("/vm/vnc/console/test-vm")
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "text/html; charset=utf-8"
    assert "VM Console" in resp.text
    assert "test-vm" in resp.text
